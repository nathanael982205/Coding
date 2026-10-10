import { api } from "../api.js";
import { state } from "../state.js";
import { esc, toast, aiOutputMeta, citedList, banner, ICON } from "../ui.js";

function freq(list, allNames, n) {
  const map = Object.fromEntries(list.map((x) => [x.name, x]));
  const names = [...new Set([...list.map((x) => x.name), ...allNames])];
  names.sort((a, b) => (map[b]?.count || 0) - (map[a]?.count || 0));
  const max = Math.max(1, ...list.map((x) => x.count));
  return names.map((name) => {
    const it = map[name];
    const c = it?.count || 0;
    const refs = (it?.studies || []).map((s) => s.ref).join("; ");
    return `<div class="freq-row ${c ? "" : "zero"}" title="${esc(refs)}"><span>${esc(name)}${c ? "" : ' <span class="badge">nicht untersucht</span>'}</span><div class="bar"><span style="width:${(c / max) * 100}%"></span></div><span class="num">${c}</span></div>`;
  }).join("") + `<div class="xs muted" style="margin-top:6px">Anzahl Studien (von ${n}), die den Parameter erheben. Hover zeigt die Studien.</div>`;
}

function refList(studies) {
  return studies.length ? studies.map((s) => `<button class="cite" data-cite-study="${s.id}">${esc(s.ref)}</button>`).join("") : '<span class="muted small">keine</span>';
}

export async function renderGaps(view, ctx) {
  const d = await api.get("/api/gaps");
  if (!ctx.isCurrent()) return;
  const n = d.n_analyzed;
  view.innerHTML = `
    <div class="page-head"><div><h1>Forschungslücken</h1><p>Systematischer Vergleich der importierten Literatur.</p></div></div>
    ${banner("warn", `<b>Wichtig:</b> Alle Aussagen beziehen sich ausschließlich auf die <b>${n} importierten und analysierten Studien</b>. Eine „Lücke innerhalb der importierten Literatur“ ist <b>kein</b> Nachweis einer Forschungslücke im gesamten Forschungsstand – dafür ist eine systematische Recherche (z. B. PubMed, SPORTDiscus, Web of Science) notwendig.`)}
    ${n === 0 ? '<div class="card empty"><h3>Noch keine analysierten Studien</h3><p>Nach dem Import und der KI-Analyse erscheinen hier die Auswertungen.</p></div>' : `
    <div class="grid two">
      <div class="card"><div class="card-head"><h3>GPS-Parameter</h3><span class="sub">Wie gut untersucht?</span></div>${freq(d.gps_variables, d.all_gps_params, n)}</div>
      <div class="card"><div class="card-head"><h3>CMJ-Parameter</h3><span class="sub">Welche selten verwendet?</span></div>${freq(d.cmj_variables, d.all_cmj_params, n)}</div>
      <div class="card"><div class="card-head"><h3>Messzeitpunkte nach Belastung</h3></div>
        ${["24h", "48h", "72h"].map((h) => `<div style="margin-bottom:10px"><div class="row"><b>${h.replace("h", " h")}</b><span class="badge ${d.timepoints[h].count ? "primary" : "warn"}">${d.timepoints[h].count} Studie(n)</span></div><div style="margin-top:4px">${refList(d.timepoints[h].studies)}</div></div>`).join("")}
        <div class="small muted">MD-Bezüge: ${Object.entries(d.md_offsets).map(([k, v]) => `${esc(k)} (${v})`).join(", ") || "–"}</div></div>
      <div class="card"><div class="card-head"><h3>Stichproben & Kombinationen</h3></div>
        <div style="margin-bottom:10px"><b>Professionelle Fußballspieler</b> <span class="badge primary">${d.professional_football.count}</span><div style="margin-top:4px">${refList(d.professional_football.studies)}</div></div>
        <div style="margin-bottom:10px"><b>GPS + CMJ kombiniert</b> <span class="badge primary">${d.combos.gps_and_cmj.count}</span><div style="margin-top:4px">${refList(d.combos.gps_and_cmj.studies)}</div></div>
        <div class="small muted">Nur GPS: ${d.combos.gps_only.count} · Nur CMJ: ${d.combos.cmj_only.count}</div>
        <div class="small muted" style="margin-top:6px">Leistungsniveaus: ${Object.entries(d.levels).map(([k, v]) => `${esc(k)} (${v})`).join(", ")}</div>
        <div class="small muted">Designs: ${Object.entries(d.designs).map(([k, v]) => `${esc(k)} (${v})`).join(", ")}</div>
        <div class="small muted">Statistik: ${Object.entries(d.stat_methods).map(([k, v]) => `${esc(k)} (${v})`).join(", ") || "–"}</div></div>
    </div>
    <div class="card" style="margin-top:16px"><div class="card-head"><h3>Von Autoren berichtete Limitationen</h3><span class="sub">${d.limitations.length} Einträge</span></div>
      <div style="max-height:320px;overflow:auto">${d.limitations.map((l) => `<div class="ai-item small"><button class="cite" data-cite-study="${l.id}" data-cite-page="${l.page || ""}">${esc(l.ref)}${l.page ? `, S. ${l.page}` : ""}</button> ${esc(l.text)}</div>`).join("") || '<div class="muted small">Keine.</div>'}</div></div>
    <div class="ai-box" style="margin-top:16px" id="g-ai"></div>`}`;
  if (n) drawAI(view.querySelector("#g-ai"), d.latest_ai, n);
}

function drawAI(box, ai, n) {
  const can = state.status?.ai_configured && n >= 2;
  const btn = `<button class="btn ${ai ? "" : "primary"}" id="g-run" ${can ? "" : "disabled"}>${ICON.spark} ${ai ? "Neu erstellen" : "KI-Lückenanalyse erstellen"}</button>`;
  if (!ai) {
    box.innerHTML = `<div class="ai-head"><h3>KI-Lückenanalyse</h3><span class="spacer"></span>${btn}</div><p class="small muted">Gut/selten untersuchte Aspekte, Widersprüche, wiederkehrende Einschränkungen und Lücken innerhalb der importierten Literatur (max. 40 relevanteste Studien).</p>`;
  } else {
    const o = ai.output;
    box.innerHTML = `<div class="ai-head"><h3>KI-Lückenanalyse</h3>${aiOutputMeta(ai)}<span class="spacer"></span>${btn}</div>
      <div class="cols-2"><div><h4>Gut untersucht</h4>${citedList(o.well_studied)}</div><div><h4>Selten untersucht</h4>${citedList(o.rarely_studied)}</div>
      <div><h4>Widersprüchliche Ergebnisse</h4>${citedList(o.contradictions)}</div><div><h4>Wiederkehrende methodische Einschränkungen</h4>${citedList(o.recurring_limitations)}</div></div>
      <h4 style="margin-top:14px">Lücken innerhalb der importierten Literatur <span class="badge warn">kein Nachweis für den Gesamtforschungsstand</span></h4>${citedList(o.gaps_in_imported_literature)}
      <h4 style="margin-top:14px">Vorschläge für ergänzende Recherche</h4><ul class="small" style="padding-left:20px;margin:6px 0 0">${(o.suggested_search_topics || []).map((x) => `<li>${esc(x)}</li>`).join("") || "<li>–</li>"}</ul>
      ${o.caveats ? `<div class="small muted" style="margin-top:10px"><b>Einschränkungen:</b> ${esc(o.caveats)}</div>` : ""}`;
  }
  box.querySelector("#g-run")?.addEventListener("click", async (e) => {
    e.target.disabled = true; e.target.innerHTML = '<span class="spinner"></span> KI arbeitet …';
    try { drawAI(box, await api.post("/api/gaps/ai"), n); } catch (err) { toast(err.message, "err"); drawAI(box, ai, n); }
  });
}
