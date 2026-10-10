import { api } from "../api.js";
import { state, toggleCompare } from "../state.js";
import { esc, demoBanner, label, scoreView, statusBadge, chapterTitle, debounce, toast } from "../ui.js";
import { openUpload } from "../app.js";

const F = () => state.libraryFilters;

function options(obj, sel, all = "Alle") {
  return `<option value="">${all}</option>` + Object.entries(obj).map(([k, v]) => `<option value="${esc(k)}" ${sel === k ? "selected" : ""}>${esc(v)}</option>`).join("");
}

export function applyFilters(list, f, searchHits) {
  return list.filter((s) => {
    if (searchHits && !searchHits[s.id]) return false;
    if (f.yearFrom && (!s.year || s.year < +f.yearFrom)) return false;
    if (f.yearTo && (!s.year || s.year > +f.yearTo)) return false;
    if (f.design && s.design_category !== f.design) return false;
    if (f.sport && (s.sport || "") !== f.sport) return false;
    if (f.level && s.level_category !== f.level) return false;
    if (f.gps === "yes" && !s.uses_gps) return false;
    if (f.gps === "no" && s.uses_gps) return false;
    if (f.cmj === "yes" && !s.uses_cmj) return false;
    if (f.cmj === "no" && s.uses_cmj) return false;
    if (f.stat && !(s.stat_methods || []).includes(f.stat)) return false;
    if (f.relMin && (s.relevance_score ?? -1) < +f.relMin) return false;
    if (f.chapter && !(s.chapters || []).includes(f.chapter)) return false;
    if (f.topic && !(s.topics || []).includes(f.topic)) return false;
    if (f.tag && !(s.user_tags || []).includes(f.tag)) return false;
    if (f.status && s.status !== f.status) return false;
    return true;
  });
}

function sortList(list, sort) {
  const by = {
    relevance: (a, b) => (b.relevance_score ?? -1) - (a.relevance_score ?? -1),
    year_desc: (a, b) => (b.year ?? 0) - (a.year ?? 0),
    year_asc: (a, b) => (a.year ?? 9999) - (b.year ?? 9999),
    title: (a, b) => (a.title || a.filename).localeCompare(b.title || b.filename),
    imported: (a, b) => b.id - a.id,
  }[sort] || ((a, b) => b.id - a.id);
  return [...list].sort(by);
}

export async function renderLibrary(view, ctx) {
  const isDemo = state.studies.length === 0;
  const f = F();
  if (ctx.params.q !== undefined) f.q = ctx.params.q;
  if (ctx.params.design !== undefined) f.design = ctx.params.design;
  if (ctx.params.topic !== undefined) f.topic = ctx.params.topic;
  const v = state.vocab;
  const sports = [...new Set(state.studies.map((s) => s.sport).filter(Boolean))].sort();
  view.innerHTML = `
    ${isDemo ? demoBanner() : ""}
    <div class="page-head">
      <div><h1>Studienbibliothek</h1><p>Alle importierten Studien – filtern, durchsuchen, öffnen und zum Vergleich auswählen.</p></div>
      <div class="btn-row">
        <button class="btn" id="lib-upload">PDFs importieren</button>
        <div class="btn-row" role="group"><button class="btn sm ${state.libraryView === "cards" ? "primary" : ""}" data-view="cards">Karten</button><button class="btn sm ${state.libraryView === "table" ? "primary" : ""}" data-view="table">Tabelle</button></div>
      </div>
    </div>
    <div class="card filter-bar">
      <div class="filters">
        <label class="field" style="grid-column: span 2">Volltextsuche (Titel, Analysen, Notizen, PDF-Text)<input class="input" id="f-q" type="search" value="${esc(f.q || "")}" placeholder="z. B. FT:CT, high-speed running, MD+2 …"></label>
        <label class="field">Jahr von<input class="input" id="f-yearFrom" type="number" value="${esc(f.yearFrom || "")}" placeholder="z. B. 2015"></label>
        <label class="field">Jahr bis<input class="input" id="f-yearTo" type="number" value="${esc(f.yearTo || "")}"></label>
        <label class="field">Forschungsdesign<select class="input" id="f-design">${options(v.design_categories, f.design)}</select></label>
        <label class="field">Sportart<select class="input" id="f-sport">${options(Object.fromEntries(sports.map((s) => [s, s])), f.sport)}</select></label>
        <label class="field">Leistungsniveau<select class="input" id="f-level">${options(v.level_categories, f.level)}</select></label>
        <label class="field">GPS-Nutzung<select class="input" id="f-gps">${options({ yes: "Mit GPS", no: "Ohne GPS" }, f.gps)}</select></label>
        <label class="field">CMJ-Nutzung<select class="input" id="f-cmj">${options({ yes: "Mit CMJ", no: "Ohne CMJ" }, f.cmj)}</select></label>
        <label class="field">Statistische Methode<select class="input" id="f-stat">${options(v.stat_methods, f.stat)}</select></label>
        <label class="field">Relevanz ab<select class="input" id="f-relMin">${options({ 30: "≥ 30", 50: "≥ 50", 70: "≥ 70", 85: "≥ 85" }, f.relMin, "Beliebig")}</select></label>
        <label class="field">Theoriekapitel<select class="input" id="f-chapter">${options(Object.fromEntries(v.chapters.map((c) => [c.key, c.title])), f.chapter)}</select></label>
        <label class="field">Thema<select class="input" id="f-topic">${options(v.topics, f.topic)}</select></label>
        <label class="field">Markierung<select class="input" id="f-tag">${options(v.user_tags, f.tag)}</select></label>
        <label class="field">Status<select class="input" id="f-status">${options(Object.fromEntries(Object.entries({ analyzed: "Analysiert", no_api: "KI ausstehend", queued: "In Warteschlange", analyzing: "Analyse läuft", error: "Fehler", needs_ocr: "OCR nötig", extracted: "Text extrahiert" })), f.status)}</select></label>
        <label class="field">Sortierung<select class="input" id="f-sort">${options({ relevance: "Relevanz", year_desc: "Jahr (neueste)", year_asc: "Jahr (älteste)", title: "Titel A–Z", imported: "Zuletzt importiert" }, f.sort || "relevance", "Standard")}</select></label>
        <div><button class="btn" id="f-reset" style="width:100%">Filter zurücksetzen</button></div>
      </div>
    </div>
    <div class="row" style="margin-bottom:12px"><span class="small muted" id="lib-count"></span><span class="spacer"></span><span class="small muted" id="lib-cmp"></span></div>
    <div id="lib-results"></div>`;

  view.querySelector("#lib-upload").addEventListener("click", openUpload);
  view.querySelectorAll("[data-view]").forEach((b) => b.addEventListener("click", () => {
    state.libraryView = b.dataset.view;
    try { localStorage.setItem("rh-libview", state.libraryView); } catch (e) { /* ignore */ }
    view.querySelectorAll("[data-view]").forEach((x) => x.classList.toggle("primary", x === b));
    draw();
  }));

  let searchHits = null;
  const runSearch = async () => {
    if (isDemo) return;
    const q = (f.q || "").trim();
    if (!q) { searchHits = null; draw(); return; }
    try { searchHits = (await api.get(`/api/search?q=${encodeURIComponent(q)}`)).studies; } catch (e) { toast(e.message, "err"); }
    draw();
  };
  const dSearch = debounce(runSearch, 350);
  view.querySelector("#f-q").addEventListener("input", (e) => { f.q = e.target.value; dSearch(); });
  ["yearFrom", "yearTo"].forEach((k) => view.querySelector(`#f-${k}`).addEventListener("input", debounce((e) => { f[k] = e.target.value; draw(); }, 300)));
  ["design", "sport", "level", "gps", "cmj", "stat", "relMin", "chapter", "topic", "tag", "status", "sort"].forEach((k) =>
    view.querySelector(`#f-${k}`).addEventListener("change", (e) => { f[k] = e.target.value; draw(); }));
  view.querySelector("#f-reset").addEventListener("click", () => { state.libraryFilters = {}; location.hash = "#/library"; renderLibrary(view, { ...ctx, params: {} }); });

  function draw() {
    const all = isDemo ? state.demo.studies : state.studies;
    const list = sortList(applyFilters(all, f, searchHits), f.sort || "relevance");
    view.querySelector("#lib-count").textContent = `${list.length} von ${all.length} Studien`;
    view.querySelector("#lib-cmp").innerHTML = state.compare.length ? `${state.compare.length} zum Vergleich ausgewählt · <a href="#/compare">Vergleich öffnen</a>` : "";
    const box = view.querySelector("#lib-results");
    if (!list.length) {
      box.innerHTML = `<div class="card empty"><h3>Keine Studien gefunden</h3><p>Filter anpassen oder neue PDFs importieren.</p></div>`;
      return;
    }
    box.innerHTML = state.libraryView === "table" ? tableView(list, searchHits) : `<div class="lib-grid">${list.map((s) => card(s, searchHits)).join("")}</div>`;
    box.querySelectorAll("[data-open]").forEach((el) => el.addEventListener("click", (e) => {
      if (e.target.closest("[data-cmp]") || e.target.closest("a")) return;
      location.hash = el.dataset.open;
    }));
    box.querySelectorAll("[data-cmp]").forEach((cb) => cb.addEventListener("click", (e) => {
      e.stopPropagation();
      const r = toggleCompare(cb.dataset.cmp);
      if (!r.ok) { toast(r.msg, "err"); cb.checked = false; }
      view.querySelector("#lib-cmp").innerHTML = state.compare.length ? `${state.compare.length} zum Vergleich ausgewählt · <a href="#/compare">Vergleich öffnen</a>` : "";
    }));
  }

  const onChange = () => { if (ctx.isCurrent() && location.hash.startsWith("#/library")) draw(); };
  document.addEventListener("studies-changed", onChange);
  window.addEventListener("hashchange", () => document.removeEventListener("studies-changed", onChange), { once: true });

  if (f.q) await runSearch(); else draw();
}

function hitBlock(s, hits) {
  const h = hits?.[s.id];
  if (!h) return "";
  const parts = [];
  if (h.analysis_hit) parts.push(`<div class="hit"><b>Analyse:</b> ${hl(h.analysis_hit)}</div>`);
  (h.page_hits || []).slice(0, 2).forEach((p) => parts.push(`<div class="hit"><a href="#/study/${s.id}?page=${p.page}" data-stop>PDF-S. ${p.page}</a>: ${hl(p.snippet)}</div>`));
  return parts.join("");
}
const hl = (snip) => esc(snip).replace(/«/g, "<mark>").replace(/»/g, "</mark>");

function card(s, hits) {
  const href = s.demo ? "#/study/demo" : `#/study/${s.id}`;
  const tags = [
    s.uses_gps ? '<span class="badge info">GPS</span>' : "",
    s.uses_cmj ? '<span class="badge info">CMJ</span>' : "",
    ...(s.topics || []).slice(0, 4).map((t) => `<span class="tag">${esc(label("topics", t))}</span>`),
    ...(s.user_tags || []).map((t) => `<span class="badge primary">${esc(label("user_tags", t))}</span>`),
  ].join("");
  return `<div class="card study-card" data-open="${href}" tabindex="0">
    ${s.demo ? "" : `<label class="cmp check xs" title="Zum Vergleich auswählen"><input type="checkbox" data-cmp="${s.id}" ${state.compare.includes(s.id) ? "checked" : ""}> Vergleich</label>`}
    <div style="padding-right:76px"><div class="title clamp-3">${esc(s.title || s.filename)}</div>
    <div class="meta">${esc(s.authors || "Autoren unbekannt")} ${s.year ? `· ${s.year}` : ""} ${s.journal ? `· <i>${esc(s.journal)}</i>` : ""}</div></div>
    <div class="row" style="gap:6px">${statusBadge(s.status)}${s.design_category ? `<span class="badge">${esc(label("design_categories", s.design_category))}</span>` : ""}${s.sample_n ? `<span class="badge">n = ${s.sample_n}</span>` : ""}${s.level_category && s.level_category !== "not_reported" ? `<span class="badge">${esc(label("level_categories", s.level_category))}</span>` : ""}</div>
    ${s.short_summary ? `<div class="summary clamp-3">${esc(s.short_summary)}</div>` : s.status_message ? `<div class="small muted clamp-2">${esc(s.status_message)}</div>` : ""}
    ${hitBlock(s, hits)}
    <div class="tags">${tags}</div>
    <div class="foot">${scoreView(s.relevance_score)}<span class="spacer"></span>${(s.chapters || []).length ? `<span class="xs muted" title="${esc((s.chapters || []).map(chapterTitle).join(" · "))}">Kapitel ${(s.chapters || []).map((c) => state.vocab.chapters.findIndex((x) => x.key === c) + 1).sort().join(", ")}</span>` : ""}</div>
  </div>`;
}

function tableView(list, hits) {
  return `<div class="table-wrap"><table class="table"><thead><tr><th></th><th>Titel</th><th>Autoren</th><th>Jahr</th><th>Design</th><th>n</th><th>GPS</th><th>CMJ</th><th>Relevanz</th><th>Status</th></tr></thead><tbody>
  ${list.map((s) => `<tr class="clickable" data-open="${s.demo ? "#/study/demo" : `#/study/${s.id}`}">
    <td>${s.demo ? "" : `<input type="checkbox" data-cmp="${s.id}" ${state.compare.includes(s.id) ? "checked" : ""} title="Vergleich">`}</td>
    <td class="clip"><div class="clamp-2" style="font-weight:500">${esc(s.title || s.filename)}</div>${hitBlock(s, hits)}</td>
    <td class="clip"><div class="clamp-2 small">${esc(s.authors || "")}</div></td><td>${s.year ?? ""}</td>
    <td class="small">${esc(s.design_category ? label("design_categories", s.design_category) : "")}</td><td>${s.sample_n ?? ""}</td>
    <td>${s.uses_gps ? "✓" : ""}</td><td>${s.uses_cmj ? "✓" : ""}</td><td>${scoreView(s.relevance_score)}</td><td>${statusBadge(s.status)}</td></tr>`).join("")}
  </tbody></table></div>`;
}
