import { api } from "../api.js";
import { state } from "../state.js";
import { esc, toast, debounce, claim, aiOutputMeta, citedList, banner, ICON } from "../ui.js";

let current = null;
const FIELD_LABELS = {
  "design.study_type": "Studientyp", "design.temporal_direction": "Prospektiv/retrospektiv", "design.duration": "Untersuchungsdauer",
  "design.setting": "Setting", "design.n_timepoints": "Anzahl Messzeitpunkte", "methods.measured_parameters": "Gemessene Parameter",
  "methods.load_variable_definitions": "Definitionen der Belastungsvariablen", "methods.cmj_device": "CMJ-Messgerät",
  "methods.gps_system": "GPS-System", "methods.measurement_timing": "Zeitpunkt der Messungen", "timepoints.description": "Messzeitpunkte",
  "methods.procedure": "Versuchsablauf", "methods.instruments": "Messinstrumente", "methods.confounders": "Störvariablen",
  "methods.statistical_methods": "Statistische Verfahren", "statistics.software": "Software", "statistics.alpha_level": "Signifikanzniveau",
  "methods.repeated_measures_handling": "Umgang mit wiederholten Messungen", variables: "Variable (Definition/Einheit)",
};

export async function renderMethods(view, ctx) {
  const topics = state.vocab.method_topics;
  current = ctx.args[0] || current || topics[0].key;
  view.innerHTML = `
    <div class="page-head"><div><h1>Methodik-Assistent</h1><p>Welche methodischen Entscheidungen werden durch welche importierten Studien gestützt? Literaturbefunde und eigene Empfehlungen sind strikt getrennt.</p></div></div>
    <div class="layout-side">
      <div class="card" style="padding:10px"><div class="side-list">${topics.map((t) => `<button data-t="${t.key}" class="${t.key === current ? "active" : ""}">${esc(t.title)}</button>`).join("")}</div></div>
      <div id="m-main"><div class="empty"><span class="spinner"></span></div></div>
    </div>`;
  view.querySelectorAll("[data-t]").forEach((b) => b.addEventListener("click", () => { location.hash = `#/methods/${b.dataset.t}`; }));
  const d = await api.get(`/api/methods/${current}`);
  if (!ctx.isCurrent()) return;
  const main = view.querySelector("#m-main");
  main.innerHTML = `
    <div class="stack">
      <div class="card">
        <div class="card-head"><h2>${esc(d.topic.title)}</h2><span class="sub">Literaturbefunde aus ${d.studies.length} Studie(n)</span></div>
        <div class="small muted" style="margin-bottom:10px">Direkt aus den Einzelanalysen übernommene Angaben (mit Seitenbeleg). Keine KI-Synthese.</div>
        ${d.studies.length ? d.studies.map((s) => `<details class="card flat" style="padding:12px;margin-bottom:8px" ${d.studies.length <= 4 ? "open" : ""}>
            <summary style="cursor:pointer;font-weight:600">${esc(s.ref)} <span class="xs muted" style="font-weight:400">– ${esc(s.title || "")}</span></summary>
            <div style="margin-top:8px">${s.entries.map((e) => `<div class="xs muted" style="margin-top:6px">${esc(FIELD_LABELS[e.field] || e.field)}</div>${claim(e, { studyId: s.study_id }).replace(/data-goto-page="(\d+)"/g, `data-cite-study="${s.study_id}" data-cite-page="$1"`)}`).join("")}</div>
          </details>`).join("") : '<div class="muted small">Keine passenden Angaben in den analysierten Studien gefunden.</div>'}
      </div>
      <div class="ai-box" id="m-ai"></div>
      <div class="card">
        <div class="card-head"><h3>Meine methodische Entscheidung</h3><span class="sub" id="m-note-state">automatische Speicherung</span></div>
        <textarea class="input" id="m-note" style="min-height:150px" placeholder="Entscheidung, Begründung, gestützt durch …">${esc(d.note?.content || "")}</textarea>
      </div>
    </div>`;
  const note = main.querySelector("#m-note");
  const save = debounce(async () => {
    try { await api.put(`/api/notes/method/${current}`, { content: note.value }); main.querySelector("#m-note-state").textContent = `gespeichert ${new Date().toLocaleTimeString("de-CH")}`; } catch (e) { toast(e.message, "err"); }
  }, 700);
  note.addEventListener("input", () => { main.querySelector("#m-note-state").textContent = "speichert …"; save(); });
  drawAI(main.querySelector("#m-ai"), d.latest_ai, d.studies.length);
}

function drawAI(box, ai, n) {
  const can = state.status?.ai_configured && n > 0;
  const btn = `<button class="btn ${ai ? "" : "primary"}" id="m-run" ${can ? "" : "disabled"}>${ICON.spark} ${ai ? "Neu erstellen" : "KI-Auswertung erstellen"}</button>`;
  if (!ai) {
    box.innerHTML = `<div class="ai-head"><h3>KI-Auswertung</h3><span class="spacer"></span>${btn}</div><p class="small muted">Fasst die Literaturbefunde zu diesem Thema zusammen und formuliert getrennt davon eigene Empfehlungen sowie offene Entscheidungen.</p>`;
  } else {
    const o = ai.output;
    box.innerHTML = `<div class="ai-head"><h3>KI-Auswertung</h3>${aiOutputMeta(ai)}<span class="spacer"></span>${btn}</div>
      <div class="cols-2">
        <div><h4>Literaturbefunde <span class="badge primary">belegt</span></h4>${citedList(o.literature_findings)}</div>
        <div><h4>Eigene Empfehlungen <span class="badge warn">KI-Empfehlung</span></h4>${banner("warn", "Empfehlungen sind keine Literaturbefunde, sondern Vorschläge der KI – kritisch prüfen.")}${citedList(o.recommendations)}</div>
      </div>
      <h4 style="margin-top:14px">Offene Entscheidungen</h4><ul class="small" style="padding-left:20px;margin:6px 0 0">${(o.open_decisions || []).map((x) => `<li>${esc(x)}</li>`).join("") || "<li>–</li>"}</ul>
      ${o.caveats ? `<div class="small muted" style="margin-top:10px"><b>Einschränkungen:</b> ${esc(o.caveats)}</div>` : ""}`;
  }
  box.querySelector("#m-run")?.addEventListener("click", async (e) => {
    e.target.disabled = true; e.target.innerHTML = '<span class="spinner"></span> KI arbeitet …';
    try { drawAI(box, await api.post(`/api/methods/${current}/ai`), n); } catch (err) { toast(err.message, "err"); drawAI(box, ai, n); }
  });
}
