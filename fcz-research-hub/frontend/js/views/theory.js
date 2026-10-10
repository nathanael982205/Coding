import { api } from "../api.js";
import { state } from "../state.js";
import { esc, toast, debounce, scoreView, label, aiOutputMeta, citedList, banner, ICON } from "../ui.js";

let current = null;

export async function renderTheory(view, ctx) {
  const chapters = state.vocab.chapters;
  current = ctx.args[0] || current || chapters[0].key;
  const counts = Object.fromEntries(chapters.map((c) => [c.key, state.studies.filter((s) => s.status === "analyzed" && (s.chapters || []).includes(c.key)).length]));
  view.innerHTML = `
    <div class="page-head"><div><h1>Theorie-Assistent</h1><p>Kapitelweise Literaturbasis, Notizen und belegte KI-Entwürfe für den theoretischen Hintergrund.</p></div>
      <button class="btn" id="t-docx">Kapitelnotizen als Word exportieren</button></div>
    <div class="layout-side">
      <div class="card" style="padding:10px"><div class="side-list">${chapters.map((c, i) => `<button data-ch="${c.key}" class="${c.key === current ? "active" : ""}"><span class="muted xs">${i + 1}</span><span>${esc(c.title)}</span><span class="n">${counts[c.key]}</span></button>`).join("")}</div>
        <div class="xs muted" style="padding:8px 10px">Zuordnung: KI-Vorschlag pro Studie, im Tab „Relevanz“ einer Studie anpassbar.</div></div>
      <div id="t-main"><div class="empty"><span class="spinner"></span></div></div>
    </div>`;
  view.querySelector("#t-docx").addEventListener("click", async () => { try { await api.download("/api/export/docx"); } catch (e) { toast(e.message, "err"); } });
  view.querySelectorAll("[data-ch]").forEach((b) => b.addEventListener("click", () => { location.hash = `#/theory/${b.dataset.ch}`; }));

  const d = await api.get(`/api/theory/${current}`);
  if (!ctx.isCurrent()) return;
  const main = view.querySelector("#t-main");
  main.innerHTML = `
    <div class="stack">
      <div class="card">
        <div class="card-head"><h2>${esc(d.chapter.title)}</h2><span class="sub">${d.studies.length} zugeordnete Studie(n), nach Relevanz priorisiert</span></div>
        ${d.studies.length ? `<div class="table-wrap" style="border:none"><table class="table"><thead><tr><th>Studie</th><th>Design</th><th>Empfehlung</th><th>Relevanz</th></tr></thead><tbody>
          ${d.studies.map((s) => `<tr class="clickable" data-id="${s.id}"><td class="clip"><div class="clamp-2" style="font-weight:500">${esc(s.title || s.filename)}</div><div class="xs muted">${esc(s.authors || "")} ${s.year ? `· ${s.year}` : ""}</div></td>
            <td class="small">${esc(label("design_categories", s.design_category || ""))}</td><td>${(s.recommendations || []).slice(0, 2).map((r) => `<span class="badge primary">${esc(label("recommendations", r))}</span>`).join(" ")}</td><td>${scoreView(s.relevance_score)}</td></tr>`).join("")}
          </tbody></table></div>` : '<div class="muted small">Noch keine analysierten Studien diesem Kapitel zugeordnet. Fehlende Literatur ist ein Hinweis für die weitere Recherche.</div>'}
      </div>
      <div class="card">
        <div class="card-head"><h3>Eigene Kapitelnotizen</h3><span class="sub" id="t-note-state">${d.note?.updated_at ? `zuletzt gespeichert ${new Date(d.note.updated_at).toLocaleString("de-CH")}` : "automatische Speicherung"}</span></div>
        <textarea class="input" id="t-note" style="min-height:180px" placeholder="Gliederungsideen, eigene Argumentation, Formulierungen …">${esc(d.note?.content || "")}</textarea>
      </div>
      <div class="ai-box" id="t-ai"></div>
    </div>`;
  main.querySelectorAll("tr[data-id]").forEach((tr) => tr.addEventListener("click", () => { location.hash = `#/study/${tr.dataset.id}`; }));
  const note = main.querySelector("#t-note");
  const save = debounce(async () => {
    try { await api.put(`/api/notes/chapter/${current}`, { content: note.value }); main.querySelector("#t-note-state").textContent = `gespeichert ${new Date().toLocaleTimeString("de-CH")}`; } catch (e) { toast(e.message, "err"); }
  }, 700);
  note.addEventListener("input", () => { main.querySelector("#t-note-state").textContent = "speichert …"; save(); });
  drawAI(main.querySelector("#t-ai"), d.latest_ai, d.studies.length);
}

function drawAI(box, ai, n) {
  const can = state.status?.ai_configured && n > 0;
  const btn = `<button class="btn ${ai ? "" : "primary"}" id="t-run" ${can ? "" : "disabled"} title="${!state.status?.ai_configured ? "KI nicht konfiguriert" : n ? "" : "Keine Studien zugeordnet"}">${ICON.spark} ${ai ? "Neu erstellen" : "KI-Synthese erstellen"}</button>`;
  if (!ai) {
    box.innerHTML = `<div class="ai-head"><h3>KI-Synthese & Textentwurf</h3><span class="spacer"></span>${btn}</div>
      <p class="small muted">Erstellt aus den zugeordneten Studien (max. 20, nach Relevanz): zentrale Erkenntnisse, Widersprüche, Argumentationsstruktur, einen belegten Textentwurf und fehlende Aspekte. Grundlage sind ausschließlich die gespeicherten Analysen.</p>`;
  } else {
    const o = ai.output;
    box.innerHTML = `<div class="ai-head"><h3>KI-Synthese & Textentwurf</h3>${aiOutputMeta(ai)}<span class="spacer"></span>${btn}</div>
      ${banner("warn", "<b>KI-Entwurf – nicht ungeprüft übernehmen.</b> Jede Aussage über die Belege prüfen (Klick öffnet die Studie auf der Seite). Gelb markierte Belege verweisen auf eine existierende Seite ohne direkt verknüpfte Analyseangabe, rote Belege sind ungültig.")}
      ${(o.prioritized_sources || []).length ? `<h4>Priorisierte Quellen</h4><div class="stack sm" style="margin:6px 0 14px">${o.prioritized_sources.map((p) => `<div class="small"><button class="cite" data-cite-study="${p.study_id}">${esc(p.ref || p.study_id)}</button> ${esc(p.reason)}</div>`).join("")}</div>` : ""}
      <div class="cols-2"><div><h4>Zentrale Erkenntnisse</h4>${citedList(o.key_insights)}</div><div><h4>Widersprüchliche Ergebnisse</h4>${citedList(o.contradictions, "Keine Widersprüche identifiziert.")}</div></div>
      <h4 style="margin-top:14px">Mögliche Argumentationsstruktur</h4><ol style="margin:6px 0 0;padding-left:20px">${(o.argument_structure || []).map((it) => `<li>${citedList([it])}</li>`).join("")}</ol>
      <h4 style="margin-top:14px">Textentwurf <span class="badge ai">KI-Entwurf</span></h4><div class="card flat" style="padding:14px;font-family:Georgia,serif;font-size:14.5px;line-height:1.7">${citedList(o.draft_paragraphs)}</div>
      <h4 style="margin-top:14px">Fehlende Literatur / Aspekte (innerhalb der importierten Studien)</h4><ul class="small" style="margin:6px 0 0;padding-left:20px">${(o.missing_literature || []).map((x) => `<li>${esc(x)}</li>`).join("") || "<li>–</li>"}</ul>
      ${o.caveats ? `<div class="small muted" style="margin-top:10px"><b>Einschränkungen:</b> ${esc(o.caveats)}</div>` : ""}`;
  }
  box.querySelector("#t-run")?.addEventListener("click", async (e) => {
    e.target.disabled = true; e.target.innerHTML = '<span class="spinner"></span> KI arbeitet … (1–3 Min.)';
    try { drawAI(box, await api.post(`/api/theory/${current}/ai`), n); } catch (err) { toast(err.message, "err"); drawAI(box, ai, n); }
  });
}
