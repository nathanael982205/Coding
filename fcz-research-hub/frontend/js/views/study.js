import { api } from "../api.js";
import { state, toggleCompare } from "../state.js";
import { esc, claim, claims, kv, banner, statusBadge, label, chapterTitle, toast, scoreView, debounce, fmtDate, ICON } from "../ui.js";
import { PdfViewer } from "../pdfviewer.js";
import { refreshStudies, startPolling } from "../app.js";

const TABS = [
  ["overview", "Überblick"], ["design", "Forschungsdesign"], ["methods", "Methodik"], ["variables", "Variablen"],
  ["results", "Ergebnisse"], ["stats", "Statistik"], ["limits", "Limitationen"], ["relevance", "Relevanz"], ["notes", "Notizen"],
];
let currentTab = "overview";
let viewer = null;

// Klick auf Seitenverweis -> PDF springt zur Seite und markiert das Zitat
document.addEventListener("click", (e) => {
  const pl = e.target.closest("[data-goto-page]");
  if (!pl || !viewer || !location.hash.startsWith("#/study/")) return;
  viewer.goto(+pl.dataset.gotoPage, pl.dataset.quote || "");
  if (window.innerWidth <= 1180) document.getElementById("pdf-pane")?.scrollIntoView({ behavior: "smooth" });
});

export async function renderStudy(view, ctx) {
  viewer?.destroy(); viewer = null;
  const id = ctx.args[0];
  let s;
  if (id === "demo") {
    if (!state.demo) state.demo = await api.get("/api/demo");
    s = { ...state.demo.studies[0], analysis: state.demo.analysis, pages: [], demo: true, notes: "", ref: "Muster et al. (2019)" };
  } else {
    s = await api.get(`/api/studies/${id}`);
  }
  if (!ctx.isCurrent()) return;
  const a = s.analysis;
  const tq = s.text_quality || {};
  const sid = s.demo ? null : s.id;

  view.innerHTML = `
    ${s.demo ? banner("demo", "<b>DEMO – fiktive Platzhalterstudie.</b> Diese Ansicht zeigt nur die Struktur der Detailseite. Alle Inhalte sind Platzhalter.") : ""}
    <div class="detail-head">
      <div class="row" style="align-items:flex-start">
        <div style="flex:1;min-width:280px">
          <div class="xs muted"><a href="#/library">← Bibliothek</a> · ${esc(s.filename)}</div>
          <div class="title" style="margin-top:4px">${esc(s.title || s.filename)}</div>
          <div class="meta">${esc(s.authors || "Autoren nicht erkannt")} ${s.year ? `· ${s.year}` : ""} ${s.journal ? `· <i>${esc(s.journal)}</i>` : ""}
            ${s.doi ? `· <a href="https://doi.org/${esc(s.doi)}" target="_blank" rel="noopener">DOI ${esc(s.doi)} ${ICON.ext.replace("<svg", '<svg style="width:11px;height:11px"')}</a>` : ""}</div>
          <div class="row" style="margin-top:8px;gap:6px">${statusBadge(s.status)}${s.page_count ? `<span class="badge">${s.page_count} Seiten</span>` : ""}
            ${tq.overall === "partial" ? '<span class="badge warn">Teilweise ohne Text</span>' : ""}${tq.overall === "needs_ocr" ? '<span class="badge warn">OCR nötig</span>' : ""}
            ${s.relevance_score != null ? `<span class="badge primary">Relevanz ${Math.round(s.relevance_score)}</span>` : ""}
            ${s.analysis_model ? `<span class="xs muted">Analyse: ${esc(s.analysis_model)} · ${fmtDate(s.analyzed_at)}</span>` : ""}</div>
        </div>
        ${s.demo ? "" : `<div class="btn-row">
          <label class="btn sm"><input type="checkbox" id="cmp-toggle" ${state.compare.includes(s.id) ? "checked" : ""}> Vergleich</label>
          <button class="btn sm" id="reanalyze" ${state.status?.ai_configured && s.status !== "needs_ocr" ? "" : "disabled"} title="${state.status?.ai_configured ? "KI-Analyse (erneut) ausführen" : "KI nicht konfiguriert"}">${a ? "Erneut analysieren" : "Analysieren"}</button>
          <button class="btn sm danger" id="delete">Löschen</button></div>`}
      </div>
      ${s.demo ? "" : `<div class="tagbar" style="margin-top:12px">${Object.entries(state.vocab.user_tags).map(([k, v]) => `<button class="tagtoggle ${(s.user_tags || []).includes(k) ? "on" : ""}" data-tag="${k}">${esc(v)}</button>`).join("")}</div>`}
    </div>
    ${s.status_message && s.status !== "analyzed" ? banner(s.status === "error" ? "err" : (s.status === "needs_ocr" || s.status === "no_api") ? "warn" : "", esc(s.status_message)) : ""}
    ${a?.meta?.omitted_pages?.length ? banner("warn", `<b>Unvollständige Analyse:</b> PDF-Seiten ${a.meta.omitted_pages.join(", ")} wurden wegen der Längenbegrenzung nicht analysiert.`) : ""}
    <div class="split">
      <div class="pane">
        <div class="tabs" id="tabs">${TABS.map(([k, l]) => `<button data-tab="${k}" class="${k === currentTab ? "active" : ""}">${l}</button>`).join("")}</div>
        <div id="tab-body"></div>
      </div>
      <div class="pane card pdf-pane" id="pdf-pane">${s.demo ? '<div class="empty"><h3>PDF-Viewer</h3><p>Hier erscheint das Original-PDF mit Seitennavigation, Suche und Markierung der belegten Textstellen.</p></div>' : ""}</div>
    </div>`;

  const body = view.querySelector("#tab-body");
  const draw = () => {
    view.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === currentTab));
    body.innerHTML = renderTab(currentTab, s, a, sid);
    bindTab(body, s);
  };
  view.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => { currentTab = b.dataset.tab; draw(); }));
  draw();

  if (!s.demo) {
    viewer = new PdfViewer(view.querySelector("#pdf-pane"), { studyId: s.id, pages: s.pages });
    viewer.load().then(() => { if (ctx.params.page) viewer.goto(+ctx.params.page); });

    view.querySelector("#cmp-toggle").addEventListener("change", (e) => {
      const r = toggleCompare(s.id);
      if (!r.ok) { toast(r.msg, "err"); e.target.checked = false; }
    });
    view.querySelectorAll("[data-tag]").forEach((b) => b.addEventListener("click", async () => {
      b.classList.toggle("on");
      const tags = [...view.querySelectorAll("[data-tag].on")].map((x) => x.dataset.tag);
      try { await api.patch(`/api/studies/${s.id}`, { user_tags: tags }); s.user_tags = tags; refreshStudies(); } catch (err) { toast(err.message, "err"); }
    }));
    view.querySelector("#reanalyze").addEventListener("click", async () => {
      if (a && !confirm("Analyse erneut ausführen? Die bisherige KI-Analyse wird ersetzt (Notizen und Markierungen bleiben erhalten).")) return;
      try { await api.post(`/api/studies/${s.id}/analyze`); toast("Analyse gestartet …"); await refreshStudies(); startPolling(); renderStudy(view, ctx); } catch (err) { toast(err.message, "err"); }
    });
    view.querySelector("#delete").addEventListener("click", async () => {
      if (!confirm(`Studie „${s.title || s.filename}“ inklusive PDF und Analyse endgültig löschen?`)) return;
      try { await api.del(`/api/studies/${s.id}`); await refreshStudies(); toast("Studie gelöscht."); location.hash = "#/library"; } catch (err) { toast(err.message, "err"); }
    });
    if (s.status === "queued" || s.status === "analyzing") waitForAnalysis(s.id, ctx, view);
  }
}

function waitForAnalysis(id, ctx, view) {
  const t = setInterval(async () => {
    if (!ctx.isCurrent()) { clearInterval(t); return; }
    const st = state.studies.find((x) => x.id === id);
    if (st && st.status !== "queued" && st.status !== "analyzing") {
      clearInterval(t);
      if (view && ctx.isCurrent()) renderStudy(view, ctx);
    }
  }, 3000);
}

function noAnalysis(s) {
  if (s.status === "needs_ocr") return banner("warn", "<b>Keine Analyse möglich:</b> Das PDF enthält keinen auslesbaren Text. Bitte OCR durchführen (z. B. <code>ocrmypdf eingabe.pdf ausgabe.pdf</code>) und die OCR-Version importieren.");
  if (s.status === "queued" || s.status === "analyzing") return `<div class="card empty"><span class="spinner"></span><h3 style="margin-top:10px">KI-Analyse läuft</h3><p>Das kann je nach Länge 1–5 Minuten dauern. Die Seite aktualisiert sich automatisch.</p></div>`;
  return `<div class="card empty"><h3>Noch keine KI-Analyse</h3><p>${state.status?.ai_configured ? "Mit „Analysieren“ starten." : "Für die Analyse <code>ANTHROPIC_API_KEY</code> in <code>.env</code> eintragen und den Server neu starten."}</p>${heuristicsBlock(s)}</div>`;
}

function heuristicsBlock(s) {
  const h = s.heuristics;
  if (!h || !h.keyword_hits) return "";
  const names = { gps: "GPS/External Load", cmj: "CMJ/Kraftmessplatte", football: "Fußball", fatigue: "Ermüdung/Recovery", internal_load: "Internal Load" };
  return `<div style="text-align:left;margin-top:16px"><h4>Regelbasierte Vorab-Erkennung <span class="badge">keine KI · ungeprüft</span></h4>
    <div class="small" style="margin-top:6px">${h.doi ? `DOI-Kandidat: <code>${esc(h.doi)}</code><br>` : ""}
    ${Object.entries(h.keyword_hits).map(([k, v]) => `${names[k] || k}: <b>${v.count}</b> Erwähnungen${v.first_page ? ` (erstmals S. ${v.first_page})` : ""}`).join("<br>")}</div></div>`;
}

function textQuality(s) {
  const tq = s.text_quality || {};
  if (!tq.page_count) return "";
  return `<div class="section"><h4>Textextraktion</h4>${kv([
    ["Ergebnis", `${tq.overall === "ok" ? '<span class="badge ok">vollständig</span>' : tq.overall === "partial" ? '<span class="badge warn">teilweise</span>' : '<span class="badge err">OCR nötig</span>'} <span class="small">${esc(tq.hint || "")}</span>`],
    ["Seiten", `${tq.pages_ok} mit Text · ${tq.pages_low_text} wenig Text · ${tq.pages_scanned} Scan/Bild · ${tq.pages_garbled || 0} fehlerhaft · ${tq.pages_empty} leer`],
    ["Gedruckte Seitenzahlen", { pdf_label: "aus PDF-Seitenlabels", heuristic: "aus Kopf-/Fußzeilen abgeleitet (prüfen)", none: "nicht erkannt – es gelten physische PDF-Seiten" }[tq.printed_page_source] || "–"],
  ])}</div>`;
}

function verificationBlock(a) {
  const v = a?.verification;
  if (!v) return "";
  return `<div class="section"><h4>Nachvollziehbarkeit</h4>
    <div class="card flat" style="padding:12px"><div class="row small" style="gap:14px">
      <span><b>${v.claims}</b> Angaben</span><span class="badge ok">${v.verified} verifiziert</span><span class="badge warn">${v.uncertain} unsicher</span><span class="badge">${v.not_reported} nicht berichtet</span>
      <span class="muted">Zitate: ${v.quote_exact} wörtlich · ${v.quote_fuzzy} nahezu · ${v.quote_not_found} nicht gefunden${v.page_corrected ? ` · ${v.page_corrected} Seite(n) korrigiert` : ""}</span></div>
      <div class="legend-row" style="margin-top:8px"><span class="badge primary">Autoren</span> Aussage der Autoren <span class="badge ai">KI-Zusammenfassung</span> / <span class="badge ai">KI-Bewertung</span> KI-eigene Formulierung · Seitenangaben = physische PDF-Seite</div>
      ${a.page_numbering_note ? `<div class="xs muted" style="margin-top:6px">Seitenhinweis der KI: ${esc(a.page_numbering_note)}</div>` : ""}</div></div>`;
}

function renderTab(tab, s, a, sid) {
  const o = { studyId: sid };
  if (tab === "notes") return notesTab(s);
  if (!a) return (tab === "overview" ? textQuality(s) : "") + noAnalysis(s);
  const C = (x) => claim(x, o);
  const L = (x) => claims(x, o);
  switch (tab) {
    case "overview": {
      const b = a.bibliographic || {};
      return `<div class="section"><h4>Kurzzusammenfassung <span class="badge ai">KI-Zusammenfassung</span></h4><div class="card flat" style="padding:14px">${esc(a.summary?.short_summary || "")}</div></div>
        <div class="section"><h4>Was wurde untersucht?</h4>${kv([["Gegenstand", C(a.summary?.what_was_studied)], ["Forschungsfrage", C(a.design?.research_question)], ["Design", `${C(a.design?.study_type)}<div style="margin-top:6px"><span class="badge">${esc(label("design_categories", a.design?.design_category))}</span></div>`]])}</div>
        <div class="section"><h4>Bibliografie</h4>${kv([["Titel", C(b.title)], ["Autoren", C(b.authors)], ["Jahr", C(b.year)], ["Journal", C(b.journal)], ["DOI", C(b.doi)], ["Keywords", C(b.keywords)], ["Forschungsgebiet", C(b.research_field)]])}</div>
        <div class="section"><h4>Themen</h4><div class="tags">${(a.topics || []).map((t) => `<span class="tag">${esc(label("topics", t))}</span>`).join("") || '<span class="muted small">–</span>'}</div></div>
        ${verificationBlock(a)}${textQuality(s)}`;
    }
    case "design": {
      const d = a.design || {}, sm = a.sample || {};
      return `<div class="section"><h4>Forschungsdesign</h4>${kv([["Forschungsfrage", C(d.research_question)], ["Hypothesen", C(d.hypotheses)], ["Studientyp", C(d.study_type)], ["Kategorie", `<span class="badge">${esc(label("design_categories", d.design_category))}</span>`], ["Prospektiv / retrospektiv", C(d.temporal_direction)], ["Untersuchungsdauer", C(d.duration)], ["Messzeitpunkte", C(d.n_timepoints)], ["Kontrollgruppe / Vergleich", C(d.control_condition)], ["Setting", C(d.setting)]])}</div>
        <div class="section"><h4>Stichprobe</h4>${kv([["Teilnehmende", C(sm.n_participants)], ["Alter", C(sm.age)], ["Geschlecht", C(sm.sex)], ["Leistungsniveau", `${C(sm.performance_level)}<div style="margin-top:6px"><span class="badge">${esc(label("level_categories", sm.level_category))}</span></div>`], ["Sportart", C(sm.sport)], ["Ein-/Ausschlusskriterien", C(sm.inclusion_exclusion)]])}</div>`;
    }
    case "methods": {
      const m = a.methods || {}, t = a.timepoints || {};
      return `<div class="section"><h4>Methodik</h4>${kv([["Messinstrumente / Geräte", C(m.instruments)], ["GPS-System", C(m.gps_system)], ["CMJ-Messgerät", C(m.cmj_device)], ["Gemessene Parameter", C(m.measured_parameters)], ["Definitionen Belastungsvariablen", C(m.load_variable_definitions)], ["Zeitpunkt der Messungen", C(m.measurement_timing)], ["Versuchsablauf", C(m.procedure)], ["Berücksichtigte Störvariablen", C(m.confounders)]])}</div>
        <div class="section"><h4>Messzeitpunkte nach Belastung</h4>${kv([["Beschreibung", C(t.description)], ["Abdeckung", ["24h", "48h", "72h"].map((h) => `<span class="badge ${t[`covers_${h}`] ? "ok" : ""}">${t[`covers_${h}`] ? "✓" : "–"} ${h.replace("h", " h")}</span>`).join(" ")], ["MD-Bezug", (t.md_offsets || []).map((x) => `<span class="tag">${esc(x)}</span>`).join(" ") || "–"]])}
        <div class="xs muted" style="margin-top:6px">Abdeckung 24/48/72 h und MD-Bezug sind KI-Klassifikationen auf Basis der belegten Angaben oben.</div></div>`;
    }
    case "variables": {
      const vars = a.variables || [];
      if (!vars.length) return '<div class="muted">Keine Variablen extrahiert.</div>';
      const groups = {};
      vars.forEach((v) => (groups[v.category] ||= []).push(v));
      return Object.entries(groups).map(([cat, list]) => `<div class="section"><h4>${esc(label("variable_categories", cat))} (${list.length})</h4>
        <div class="table-wrap"><table class="table"><thead><tr><th>Variable</th><th>Definition / Schwelle</th><th>Einheit</th><th>Gerät</th><th>Beleg</th></tr></thead><tbody>
        ${list.map((v) => `<tr><td style="font-weight:500">${esc(v.name)}</td><td class="clip">${esc(v.definition)}</td><td>${esc(v.unit)}</td><td class="small">${esc(v.device)}</td>
          <td class="nowrap">${v.status === "verified" ? '<span class="badge ok">verifiziert</span>' : v.status === "uncertain" ? '<span class="badge warn">unsicher</span>' : '<span class="badge">n. b.</span>'}
          ${v.page ? `<button class="page-link" data-goto-page="${v.page}" data-quote="${esc(v.quote || "")}">S. ${v.page}${v.page_label ? ` · ${esc(v.page_label)}` : ""}</button>` : ""}
          ${v.check?.note ? `<div class="check-note">${esc(v.check.note)}</div>` : ""}</td></tr>`).join("")}
        </tbody></table></div></div>`).join("");
    }
    case "results": {
      const r = a.results || {};
      return `<div class="section"><h4>Wichtigste Ergebnisse</h4><div class="card flat" style="padding:14px">${L(r.key_findings)}</div></div>
        <div class="section"><h4>Unterschiede zwischen Messzeitpunkten</h4><div class="card flat" style="padding:14px">${L(r.timepoint_differences)}</div></div>
        <div class="section"><h4>Neuromuskuläre Ermüdung & Regeneration</h4><div class="card flat" style="padding:14px">${L(r.fatigue_recovery_statements)}</div></div>
        <div class="section"><h4>Praktische Bedeutung</h4><div class="card flat" style="padding:14px">${C(r.practical_significance)}</div></div>`;
    }
    case "stats": {
      const r = a.results || {}, m = a.methods || {}, st = a.statistics || {};
      return `<div class="section"><h4>Statistische Verfahren</h4>${kv([["Verfahren", C(m.statistical_methods)], ["Kategorien", (st.method_tags || []).map((t) => `<span class="tag">${esc(label("stat_methods", t))}</span>`).join(" ") || "–"], ["Umgang mit wiederholten Messungen", C(m.repeated_measures_handling)], ["Software", C(st.software)], ["Signifikanzniveau", C(st.alpha_level)]])}</div>
        <div class="section"><h4>Effektgrößen</h4><div class="card flat" style="padding:14px">${L(r.effect_sizes)}</div></div>
        <div class="section"><h4>Korrelationen</h4><div class="card flat" style="padding:14px">${L(r.correlations)}</div></div>
        <div class="section"><h4>Konfidenzintervalle</h4><div class="card flat" style="padding:14px">${L(r.confidence_intervals)}</div></div>
        <div class="section"><h4>Signifikanzwerte</h4><div class="card flat" style="padding:14px">${L(r.significance)}</div></div>`;
    }
    case "limits": {
      const c = a.critical || {};
      return `<div class="section"><h4>Limitationen laut Autoren</h4><div class="card flat" style="padding:14px">${L(c.limitations_reported)}</div></div>
        ${banner("", "Die folgenden Punkte sind <b>methodische Bewertungen der KI</b> – keine Aussagen der Autoren. Bitte kritisch prüfen.")}
        <div class="section"><h4>Stärken</h4><div class="card flat" style="padding:14px">${L(c.strengths)}</div></div>
        <div class="section"><h4>Methodische Schwächen</h4><div class="card flat" style="padding:14px">${L(c.weaknesses)}</div></div>
        <div class="section"><h4>Übertragbarkeit auf professionelle Fußballspieler</h4><div class="card flat" style="padding:14px">${C(c.transferability)}</div></div>
        <div class="section"><h4>Vergleichbarkeit mit der eigenen Forschungsfrage</h4><div class="card flat" style="padding:14px">${C(c.comparability_to_thesis)}</div></div>
        <div class="section"><h4>Offene Forschungsfragen</h4><div class="card flat" style="padding:14px">${L(c.open_questions)}</div></div>`;
    }
    case "relevance": return relevanceTab(s, a);
    default: return "";
  }
}

function relevanceTab(s, a) {
  const rel = a.relevance || {};
  const w = state.vocab.relevance_weights, lb = state.vocab.relevance_labels;
  const chapters = s.chapter_override ?? rel.chapters ?? [];
  return `${banner("", "Der Relevanz-Score ist eine <b>interne Einschätzung der Passung zur Masterarbeit</b> – keine objektive Bewertung der wissenschaftlichen Qualität.")}
    <div class="grid two">
      <div class="card"><div class="kpi-label">Gesamtscore (gewichtet berechnet)</div><div class="big-score">${s.relevance_score != null ? Math.round(s.relevance_score) : "–"}<span class="muted" style="font-size:18px"> / 100</span></div>
        <div class="xs muted">${esc(a.meta?.relevance_formula || "")}</div>
        <div class="tags" style="margin-top:10px">${(rel.recommendations || []).map((r) => `<span class="badge primary">${esc(label("recommendations", r))}</span>`).join("")}</div></div>
      <div class="card stack sm">${Object.keys(w).map((k) => {
        const sc = rel[k]?.score ?? 0;
        return `<div class="subscore"><span class="small" style="font-weight:500">${esc(lb[k])} <span class="muted">(${Math.round(w[k] * 100)} %)</span></span><span class="small" style="text-align:right;font-weight:600">${sc}</span><div class="bar"><span style="width:${sc}%"></span></div><div class="xs muted" style="grid-column:1/-1">${esc(rel[k]?.rationale || "")}</div></div>`;
      }).join("")}</div>
    </div>
    <div class="section" style="margin-top:16px"><h4>Begründung <span class="badge ai">KI-Bewertung</span></h4><div class="card flat" style="padding:14px">${esc(rel.overall_rationale || "")}</div></div>
    <div class="section"><h4>Zuordnung zu Theoriekapiteln ${s.chapter_override ? '<span class="badge warn">manuell angepasst</span>' : '<span class="badge ai">KI-Vorschlag</span>'}</h4>
      <div class="card flat stack sm" style="padding:14px">${state.vocab.chapters.map((c) => `<label class="check"><input type="checkbox" data-chapter="${c.key}" ${chapters.includes(c.key) ? "checked" : ""} ${s.demo ? "disabled" : ""}> ${esc(c.title)}</label>`).join("")}
      ${s.demo ? "" : `<div class="btn-row" style="margin-top:6px"><button class="btn sm primary" id="save-chapters">Zuordnung speichern</button>${s.chapter_override ? '<button class="btn sm" id="reset-chapters">KI-Vorschlag wiederherstellen</button>' : ""}</div>`}</div></div>`;
}

function notesTab(s) {
  return `<div class="section"><h4>Persönliche Notizen</h4>
    <textarea class="input" id="notes" style="min-height:320px" placeholder="Eigene Gedanken, Zitate, Verwendungsideen …" ${s.demo ? "disabled" : ""}>${esc(s.notes || "")}</textarea>
    <div class="xs muted" id="notes-state" style="margin-top:6px">Notizen werden automatisch lokal gespeichert und sind in der Volltextsuche enthalten.</div></div>`;
}

function bindTab(body, s) {
  const notes = body.querySelector("#notes");
  if (notes && !s.demo) {
    const save = debounce(async () => {
      try { await api.patch(`/api/studies/${s.id}`, { notes: notes.value }); s.notes = notes.value; body.querySelector("#notes-state").textContent = `Gespeichert ${new Date().toLocaleTimeString("de-CH")}`; } catch (e) { toast(e.message, "err"); }
    }, 700);
    notes.addEventListener("input", () => { body.querySelector("#notes-state").textContent = "Speichert …"; save(); });
  }
  body.querySelector("#save-chapters")?.addEventListener("click", async () => {
    const sel = [...body.querySelectorAll("[data-chapter]:checked")].map((c) => c.dataset.chapter);
    try { const r = await api.patch(`/api/studies/${s.id}`, { chapter_override: sel }); s.chapter_override = r.chapter_override; toast("Kapitelzuordnung gespeichert."); refreshStudies(); body.innerHTML = renderTab("relevance", s, s.analysis, s.id); bindTab(body, s); } catch (e) { toast(e.message, "err"); }
  });
  body.querySelector("#reset-chapters")?.addEventListener("click", async () => {
    try { const r = await api.patch(`/api/studies/${s.id}`, { chapter_override: null }); s.chapter_override = r.chapter_override; refreshStudies(); body.innerHTML = renderTab("relevance", s, s.analysis, s.id); bindTab(body, s); } catch (e) { toast(e.message, "err"); }
  });
}

export { chapterTitle, scoreView };
