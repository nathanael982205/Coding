import { api } from "../api.js";
import { state } from "../state.js";
import { esc, toast, debounce, demoBanner } from "../ui.js";

const DEFAULT_COLS = ["ref", "title", "design", "n", "level", "gps_variables", "cmj_variables", "md_offsets", "stat_tags", "key_findings", "relevance", "chapters"];
let cols = (() => { try { return JSON.parse(localStorage.getItem("rh-matrix-cols")) || DEFAULT_COLS; } catch (e) { return DEFAULT_COLS; } })();
let sort = { key: "relevance", dir: -1 };
let filter = "";

export async function renderMatrix(view, ctx) {
  const data = await api.get("/api/matrix");
  if (!ctx.isCurrent()) return;
  const colLabel = Object.fromEntries(data.columns.map((c) => [c.key, c.label]));
  view.innerHTML = `
    ${state.studies.length ? "" : demoBanner()}
    <div class="page-head">
      <div><h1>Literaturmatrix</h1><p>Strukturierte Übersicht aller Studien. Werte mit [PDF-S. n] sind belegt; „(unsicher)“ bitte im Original prüfen.</p></div>
      <div class="btn-row">
        <button class="btn" data-exp="xlsx">Excel</button><button class="btn" data-exp="csv">CSV</button>
        <button class="btn" data-exp="json">JSON</button><button class="btn" data-exp="bibtex">BibTeX</button><button class="btn" data-exp="ris">RIS</button>
      </div>
    </div>
    <div class="card filter-bar">
      <div class="row">
        <input class="input" id="m-filter" type="search" placeholder="Matrix filtern (alle sichtbaren Spalten) …" value="${esc(filter)}" style="max-width:420px">
        <span class="spacer"></span>
        <details><summary class="btn sm">Spalten wählen</summary>
          <div class="card" style="position:absolute;right:28px;z-index:30;margin-top:6px;max-height:60vh;overflow:auto;display:grid;grid-template-columns:1fr 1fr;gap:4px 16px;width:min(520px,90vw)">
            ${data.columns.map((c) => `<label class="check small"><input type="checkbox" data-col="${c.key}" ${cols.includes(c.key) ? "checked" : ""}> ${esc(c.label)}</label>`).join("")}
          </div></details>
      </div>
    </div>
    <div class="small muted" id="m-count" style="margin-bottom:8px"></div>
    <div class="table-wrap" style="max-height:calc(100vh - 290px)" id="m-table"></div>`;

  view.querySelectorAll("[data-exp]").forEach((b) => b.addEventListener("click", async () => {
    b.disabled = true;
    try { await api.download(`/api/export/${b.dataset.exp}`); } catch (e) { toast(e.message, "err"); }
    b.disabled = false;
  }));
  view.querySelector("#m-filter").addEventListener("input", debounce((e) => { filter = e.target.value; draw(); }, 200));
  view.querySelectorAll("[data-col]").forEach((c) => c.addEventListener("change", () => {
    cols = data.columns.map((x) => x.key).filter((k) => view.querySelector(`[data-col="${k}"]`).checked);
    try { localStorage.setItem("rh-matrix-cols", JSON.stringify(cols)); } catch (e) { /* ignore */ }
    draw();
  }));

  function draw() {
    const f = filter.toLowerCase().trim();
    let rows = data.rows.filter((r) => !f || cols.some((k) => String(r[k] ?? "").toLowerCase().includes(f)));
    rows = [...rows].sort((a, b) => {
      const x = a[sort.key], y = b[sort.key];
      if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1;
      return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y))) * sort.dir;
    });
    view.querySelector("#m-count").textContent = `${rows.length} von ${data.rows.length} Studien`;
    const box = view.querySelector("#m-table");
    if (!data.rows.length) { box.innerHTML = '<div class="empty"><h3>Noch keine Studien</h3><p>Importierte und analysierte Studien erscheinen hier.</p></div>'; return; }
    box.innerHTML = `<table class="table"><thead><tr>${cols.map((k) => `<th class="sortable" data-sort="${k}">${esc(colLabel[k])}${sort.key === k ? (sort.dir > 0 ? " ▲" : " ▼") : ""}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((r) => `<tr class="clickable" data-id="${r.id}">${cols.map((k) => `<td class="${["title", "key_findings", "research_question", "limitations", "statistics", "sample_desc", "timepoints"].includes(k) ? "clip" : ""}"><div class="${k === "key_findings" || k === "limitations" ? "clamp-3" : ""} small">${fmt(k, r[k])}</div></td>`).join("")}</tr>`).join("")}</tbody></table>`;
    box.querySelectorAll("[data-sort]").forEach((th) => th.addEventListener("click", () => {
      sort = { key: th.dataset.sort, dir: sort.key === th.dataset.sort ? -sort.dir : (th.dataset.sort === "relevance" || th.dataset.sort === "year" ? -1 : 1) };
      draw();
    }));
    box.querySelectorAll("tr[data-id]").forEach((tr) => tr.addEventListener("click", () => { location.hash = `#/study/${tr.dataset.id}`; }));
  }
  draw();
}

function fmt(k, v) {
  if (v == null || v === "") return '<span class="muted">–</span>';
  if (k === "relevance") return `<b>${Math.round(v)}</b>`;
  return esc(v).replace(/\[PDF-S\. ([^\]]+)\]/g, '<span class="badge primary">S. $1</span>').replace(/\(unsicher\)/g, '<span class="badge warn">unsicher</span>');
}
