import { api } from "../api.js";
import { state, toggleCompare, saveCompare } from "../state.js";
import { esc, claim, claims, label, toast, banner, aiOutputMeta, citedList, ICON } from "../ui.js";

export async function renderCompare(view, ctx) {
  const analyzed = state.studies.filter((s) => s.status === "analyzed");
  state.compare = state.compare.filter((id) => analyzed.some((s) => s.id === id));
  saveCompare();
  view.innerHTML = `
    <div class="page-head"><div><h1>Studienvergleich</h1><p>2–5 analysierte Studien nebeneinander. <span class="badge ok">grün</span> = Übereinstimmung, <span class="badge warn">gelb</span> = Unterschied (bei kategorialen Merkmalen).</p></div></div>
    <div class="card" style="margin-bottom:16px">
      <div class="card-head"><h3>Auswahl (${state.compare.length}/5)</h3><input class="input" id="c-filter" type="search" placeholder="Studien filtern …" style="max-width:300px"></div>
      <div id="c-pick" style="max-height:220px;overflow:auto" class="stack sm"></div>
    </div>
    <div id="c-out"></div>`;

  const pick = view.querySelector("#c-pick");
  const drawPick = (f = "") => {
    const list = analyzed.filter((s) => !f || (s.title || s.filename).toLowerCase().includes(f) || (s.authors || "").toLowerCase().includes(f));
    pick.innerHTML = list.length ? list.map((s) => `<label class="check small" style="padding:3px 0"><input type="checkbox" data-id="${s.id}" ${state.compare.includes(s.id) ? "checked" : ""}> <span><b>${esc((s.authors || "").split(/[,;]/)[0])}${s.year ? ` (${s.year})` : ""}</b> – ${esc(s.title || s.filename)}</span></label>`).join("")
      : '<div class="muted small">Keine analysierten Studien vorhanden.</div>';
    pick.querySelectorAll("[data-id]").forEach((cb) => cb.addEventListener("change", () => {
      const r = toggleCompare(cb.dataset.id);
      if (!r.ok) { toast(r.msg, "err"); cb.checked = false; return; }
      view.querySelector(".card-head h3").textContent = `Auswahl (${state.compare.length}/5)`;
      drawTable();
    }));
  };
  view.querySelector("#c-filter").addEventListener("input", (e) => drawPick(e.target.value.toLowerCase()));
  drawPick();

  async function drawTable() {
    const out = view.querySelector("#c-out");
    if (state.compare.length < 2) { out.innerHTML = '<div class="card empty"><h3>Mindestens zwei Studien auswählen</h3><p>Auswahl oben oder über die Checkbox „Vergleich“ in der Bibliothek.</p></div>'; return; }
    out.innerHTML = '<div class="empty"><span class="spinner"></span></div>';
    let t;
    try { t = await api.post("/api/compare", { ids: state.compare }); } catch (e) { out.innerHTML = banner("err", esc(e.message)); return; }
    const S = t.studies;
    const cat = (key) => {
      const vals = S.map((s) => JSON.stringify(s.cells._categorical?.[key] ?? null));
      if (vals.some((v) => v === "null" || v === "[]")) return "";
      return new Set(vals).size === 1 ? "cmp-same" : "cmp-diff";
    };
    const shared = (key) => {
      const sets = S.map((s) => new Set(s.cells[key].items));
      return new Set([...sets[0]].filter((x) => sets.every((st) => st.has(x))));
    };
    const sharedGps = shared("gps"), sharedCmj = shared("cmj");
    const chips = (items, sh) => items.length ? items.map((x) => `<span class="tag ${sh.has(x) ? "chip-shared" : ""}">${esc(x)}</span>`).join(" ") : '<span class="muted small">keine</span>';
    const o = { };
    const cell = (s, key) => {
      const c = s.cells[key];
      switch (key) {
        case "design": return `<span class="badge">${esc(label("design_categories", s.cells._categorical.design))}</span>${claim(c, { studyId: s.id })}`;
        case "level": return `<span class="badge">${esc(label("level_categories", s.cells._categorical.level))}</span>${claim(c, { studyId: s.id })}`;
        case "gps": return chips(c.items, sharedGps);
        case "cmj": return chips(c.items, sharedCmj);
        case "timepoints": return `${(s.cells._categorical.timepoints || []).map((x) => `<span class="tag">${esc(x)}</span>`).join(" ")}${claim(c, { studyId: s.id })}`;
        case "statistics": return `${(s.cells._categorical.statistics || []).map((x) => `<span class="tag">${esc(label("stat_methods", x))}</span>`).join(" ")}${claim(c, { studyId: s.id })}`;
        case "findings": case "limitations": return claims(c.slice(0, 5), { studyId: s.id });
        case "relevance": return `<b style="font-size:18px">${c.score != null ? Math.round(c.score) : "–"}</b><div class="tags" style="margin-top:4px">${(c.recommendations || []).map((r) => `<span class="badge primary">${esc(label("recommendations", r))}</span>`).join("")}</div>`;
        default: return claim(c, { studyId: s.id });
      }
    };
    const mark = { design: cat("design"), level: cat("level"), timepoints: cat("timepoints"), statistics: cat("statistics"), participants: cat("participants") };
    out.innerHTML = `
      <div class="table-wrap" style="max-height:70vh"><table class="table cmp-table">
        <thead><tr><th style="position:sticky;left:0;z-index:2">Dimension</th>${S.map((s) => `<th style="white-space:normal;min-width:240px"><a href="#/study/${s.id}">${esc(s.ref)}</a><div class="xs muted clamp-2" style="font-weight:400">${esc(s.title || "")}</div></th>`).join("")}</tr></thead>
        <tbody>${t.dimensions.map((d) => `<tr><td class="dim">${esc(d.label)}${mark[d.key] === "cmp-same" ? '<div><span class="badge ok">gleich</span></div>' : mark[d.key] === "cmp-diff" ? '<div><span class="badge warn">unterschiedlich</span></div>' : ""}${d.key === "gps" || d.key === "cmj" ? '<div class="xs muted" style="font-weight:400">grün = in allen Studien</div>' : ""}</td>
          ${S.map((s) => `<td class="${mark[d.key] || ""}">${cell(s, d.key)}</td>`).join("")}</tr>`).join("")}</tbody>
      </table></div>
      <div class="xs muted" style="margin-top:6px">Seitenverweise öffnen die jeweilige Studie. Übereinstimmungen basieren auf KI-Klassifikationen der Einzelanalysen.</div>
      <div class="ai-box" style="margin-top:16px" id="c-ai"></div>`;
    drawAI(t.latest_ai);
  }

  function drawAI(ai) {
    const box = view.querySelector("#c-ai");
    if (!box) return;
    const btn = `<button class="btn ${ai ? "" : "primary"}" id="c-run" ${state.status?.ai_configured ? "" : "disabled title='KI nicht konfiguriert'"}>${ICON.spark} ${ai ? "Neu erstellen" : "KI-Vergleich erstellen"}</button>`;
    if (!ai) {
      box.innerHTML = `<div class="ai-head"><h3>KI-Zusammenfassung</h3><span class="spacer"></span>${btn}</div><p class="small muted">„Was zeigen diese Studien gemeinsam, wo widersprechen sie sich und welche methodischen Unterschiede könnten dies erklären?“ – ausschließlich auf Basis der gespeicherten Analysen dieser Studien, mit Seitenbelegen.</p>`;
    } else {
      const o = ai.output;
      box.innerHTML = `<div class="ai-head"><h3>KI-Zusammenfassung</h3>${aiOutputMeta(ai)}<span class="spacer"></span>${btn}</div>
        <div class="cols-2"><div><h4>Gemeinsamkeiten</h4>${citedList(o.commonalities)}</div><div><h4>Widersprüche</h4>${citedList(o.contradictions)}</div>
        <div><h4>Methodische Unterschiede</h4>${citedList(o.methodological_differences)}</div><div><h4>Mögliche Erklärungen</h4>${citedList(o.possible_explanations)}</div></div>
        ${o.caveats ? `<div class="small muted" style="margin-top:10px"><b>Einschränkungen:</b> ${esc(o.caveats)}</div>` : ""}`;
    }
    box.querySelector("#c-run")?.addEventListener("click", async (e) => {
      e.target.disabled = true; e.target.innerHTML = '<span class="spinner"></span> KI arbeitet …';
      try { drawAI(await api.post("/api/compare/ai", { ids: state.compare })); } catch (err) { toast(err.message, "err"); drawAI(ai); }
    });
  }
  drawTable();
}
