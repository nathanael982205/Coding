import { api } from "../api.js";
import { state } from "../state.js";
import { esc, banner, demoBanner, label, scoreView, statusBadge } from "../ui.js";
import { barChart, destroyCharts } from "../charts.js";
import { openUpload } from "../app.js";

export async function renderDashboard(view, ctx) {
  destroyCharts();
  const isDemo = state.studies.length === 0;
  const stats = isDemo ? state.demo?.stats : await api.get("/api/dashboard");
  if (!ctx.isCurrent()) return;
  if (!stats) { view.innerHTML = '<div class="empty">Keine Daten.</div>'; return; }
  const studies = isDemo ? state.demo.studies : state.studies;
  const top = studies.filter((s) => s.status === "analyzed").sort((a, b) => (b.relevance_score ?? 0) - (a.relevance_score ?? 0)).slice(0, 6);
  const recent = [...studies].sort((a, b) => (b.id) - (a.id)).slice(0, 6);
  const kpi = (lbl, val, foot = "", text = false) => `<div class="card kpi-card"><div class="kpi-label">${lbl}</div><div class="kpi-value ${text ? "text" : ""}">${val}</div>${foot ? `<div class="kpi-foot">${foot}</div>` : ""}</div>`;
  const topDesign = Object.entries(stats.by_design || {})[0];
  const topTopic = Object.entries(stats.topics || {})[0];

  view.innerHTML = `
    ${isDemo ? demoBanner() : ""}
    ${!isDemo && !state.status?.ai_configured ? banner("warn", "<b>KI nicht konfiguriert.</b> Gespeicherte Analysen werden angezeigt; neue PDFs werden importiert und extrahiert, die KI-Analyse startet, sobald <code>ANTHROPIC_API_KEY</code> in <code>.env</code> gesetzt ist (siehe Einstellungen).") : ""}
    ${!isDemo && stats.needs_ocr ? banner("warn", `<b>${stats.needs_ocr} PDF(s) benötigen OCR.</b> Diese Dokumente enthalten keinen auslesbaren Text und können nicht verlässlich analysiert werden.`) : ""}
    <div class="page-head">
      <div><h1>Dashboard</h1><p>${isDemo ? "Beispielansicht mit fiktiven Werten – nach dem Import erscheinen hier ausschließlich Kennzahlen aus Ihren Studien." : "Überblick über die importierte Literatur – alle Kennzahlen stammen aus den real importierten Studien."}</p></div>
      <div class="btn-row"><button class="btn" id="dash-upload">PDFs importieren</button><a class="btn" href="#/library">Zur Bibliothek</a></div>
    </div>
    <div class="grid kpi">
      ${kpi("Importierte Studien", stats.total, stats.pending ? `${stats.pending} ausstehend` : "")}
      ${kpi("Vollständig analysiert", stats.analyzed, stats.errors ? `${stats.errors} mit Fehler` : "")}
      ${kpi("Hochrelevant (≥ 70)", stats.high_relevance)}
      ${kpi("Mit CMJ-Messung", stats.with_cmj)}
      ${kpi("Mit GPS-Daten", stats.with_gps)}
      ${kpi("Häufigstes Design", topDesign ? esc(topDesign[0]) : "–", topDesign ? `${topDesign[1]} Studie(n)` : "", true)}
      ${kpi("Häufigstes Thema", topTopic ? esc(label("topics", topTopic[0])) : "–", topTopic ? `${topTopic[1]} Studie(n)` : "", true)}
    </div>
    <div class="grid two" style="margin-top:16px">
      <div class="card"><div class="card-head"><h3>Veröffentlichungen nach Jahr</h3><span class="sub">Analysierte Studien</span></div><div class="chart-box"><canvas id="c-year"></canvas></div></div>
      <div class="card"><div class="card-head"><h3>Forschungsdesigns</h3><span class="sub">Klick filtert die Bibliothek</span></div><div class="chart-box"><canvas id="c-design"></canvas></div></div>
      <div class="card"><div class="card-head"><h3>Untersuchte Variablen</h3><span class="sub">GPS & CMJ, normalisiert</span></div><div class="chart-box tall"><canvas id="c-vars"></canvas></div></div>
      <div class="card"><div class="card-head"><h3>Relevanz-Score-Verteilung</h3><span class="sub">Interne Passung, keine Qualitätsbewertung</span></div><div class="chart-box tall"><canvas id="c-rel"></canvas></div></div>
      <div class="card"><div class="card-head"><h3>Themenverteilung</h3><span class="sub">Klick filtert die Bibliothek</span></div><div class="chart-box tall"><canvas id="c-topics"></canvas></div></div>
      <div class="card"><div class="card-head"><h3>Relevanteste Studien</h3><a class="small" href="#/library">alle</a></div>
        ${top.length ? `<div class="stack sm">${top.map((s) => `<a href="${s.demo ? "#/study/demo" : `#/study/${s.id}`}" class="row" style="justify-content:space-between;color:inherit;text-decoration:none;padding:6px 0;border-bottom:1px solid var(--border)">
          <span style="min-width:0;flex:1"><span class="clamp-2" style="font-weight:500">${esc(s.title || s.filename)}</span><span class="xs muted">${esc(s.authors || "")} ${s.year ? `· ${s.year}` : ""}</span></span>${scoreView(s.relevance_score)}</a>`).join("")}</div>` : '<div class="muted small">Noch keine analysierten Studien.</div>'}
      </div>
    </div>
    <div class="card" style="margin-top:16px"><div class="card-head"><h3>Zuletzt importiert</h3></div>
      ${recent.length ? `<div class="table-wrap" style="border:none"><table class="table"><thead><tr><th>Titel / Datei</th><th>Status</th><th>Seiten</th><th>Relevanz</th></tr></thead><tbody>
      ${recent.map((s) => `<tr class="clickable" data-href="${s.demo ? "#/study/demo" : `#/study/${s.id}`}"><td class="clip"><div class="clamp-2">${esc(s.title || s.filename)}</div><div class="xs muted">${esc(s.filename)}</div></td><td>${statusBadge(s.status)}</td><td>${s.page_count ?? ""}</td><td>${scoreView(s.relevance_score)}</td></tr>`).join("")}
      </tbody></table></div>` : '<div class="muted small">Noch nichts importiert.</div>'}
    </div>`;

  view.querySelector("#dash-upload").addEventListener("click", openUpload);
  view.querySelectorAll("tr[data-href]").forEach((tr) => tr.addEventListener("click", () => { location.hash = tr.dataset.href; }));

  const year = stats.by_year || {};
  barChart(view.querySelector("#c-year"), Object.keys(year), Object.values(year));
  const designs = stats.by_design || {};
  const designKeyByLabel = Object.fromEntries(Object.entries(state.vocab?.design_categories || {}).map(([k, v]) => [v, k]));
  barChart(view.querySelector("#c-design"), Object.keys(designs), Object.values(designs), { horizontal: true, onClick: (lbl) => { if (!isDemo) location.hash = `#/library?design=${designKeyByLabel[lbl] || ""}`; } });
  const vars = stats.variables || {};
  barChart(view.querySelector("#c-vars"), Object.keys(vars), Object.values(vars), { horizontal: true });
  const rel = stats.relevance_bins || {};
  barChart(view.querySelector("#c-rel"), Object.keys(rel), Object.values(rel));
  const topics = stats.topics || {};
  barChart(view.querySelector("#c-topics"), Object.keys(topics).map((k) => label("topics", k)), Object.values(topics), {
    horizontal: true, onClick: (_l, i) => { if (!isDemo) location.hash = `#/library?topic=${Object.keys(topics)[i]}`; },
  });
}
