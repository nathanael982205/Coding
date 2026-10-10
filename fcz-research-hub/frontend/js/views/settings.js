import { api } from "../api.js";
import { state } from "../state.js";
import { esc, toast, kv, banner, statusBadge } from "../ui.js";
import { refreshStatus, refreshStudies, startPolling } from "../app.js";

export async function renderSettings(view, ctx) {
  await refreshStatus();
  const [settings, backups] = await Promise.all([api.get("/api/settings"), api.get("/api/backups")]);
  if (!ctx.isCurrent()) return;
  const st = state.status;
  const pending = state.studies.filter((s) => ["extracted", "no_api", "error"].includes(s.status)).length;
  view.innerHTML = `
    <div class="page-head"><div><h1>Einstellungen</h1><p>KI-Anbindung, Kontext der Masterarbeit, Export, Backup und Datenschutz.</p></div></div>
    <div class="grid two">
      <div class="card stack sm">
        <h3>KI-Anbindung (Claude API)</h3>
        ${kv([
          ["Status", st.ai_configured ? '<span class="badge ok">konfiguriert</span>' : '<span class="badge warn">nicht konfiguriert</span>'],
          ["Modell", `<code>${esc(st.model)}</code>`], ["Effort", `<code>${esc(st.effort)}</code>`],
          ["Refusal-Fallback", st.refusal_fallback ? "aktiv (server-seitig)" : "aus"],
          ["Datenordner", `<code class="small">${esc(st.data_dir)}</code>`],
        ])}
        ${st.ai_configured ? "" : banner("warn", "API-Schlüssel in <code>.env</code> eintragen (<code>ANTHROPIC_API_KEY=...</code>) und den Server neu starten. Der Schlüssel bleibt im Backend und erscheint nie im Browser.")}
        <div class="btn-row"><button class="btn" id="s-test" ${st.ai_configured ? "" : "disabled"}>Verbindung testen</button>
          <button class="btn" id="s-pending" ${st.ai_configured && pending ? "" : "disabled"}>Ausstehende analysieren (${pending})</button>
          <button class="btn" id="s-all" ${st.ai_configured && state.studies.length ? "" : "disabled"}>Alle neu analysieren</button></div>
        <div class="small muted" id="s-test-out"></div>
      </div>
      <div class="card stack sm">
        <h3>Datenschutz</h3>
        <ul class="small" style="margin:0;padding-left:18px;line-height:1.7">
          <li>An die Claude API wird ausschließlich der extrahierte Text der von Ihnen importierten wissenschaftlichen PDFs bzw. daraus abgeleitete Analysen gesendet.</li>
          <li>Die Anwendung verarbeitet <b>keine FCZ-Spieler- oder Vereinsdaten</b>. Bitte keine internen Dokumente (WIMU-/ForceDecks-Exporte, Spielerlisten) importieren.</li>
          <li>Alle Daten (PDFs, Datenbank, Notizen) liegen lokal im Datenordner.</li>
          <li>Der Server lauscht standardmäßig nur auf <code>127.0.0.1</code> (nicht im Netzwerk erreichbar).</li>
        </ul>
      </div>
      <div class="card stack sm" style="grid-column:1/-1">
        <h3>Kontext der Masterarbeit</h3>
        <p class="small muted">Dieser Text steuert die Relevanzbewertung und die Assistenten. Änderungen wirken auf künftige Analysen (bestehende ggf. neu analysieren).</p>
        <textarea class="input" id="s-ctx" style="min-height:140px">${esc(settings.thesis_context)}</textarea>
        <div class="btn-row"><button class="btn primary" id="s-ctx-save">Speichern</button><button class="btn" id="s-ctx-reset">Standard wiederherstellen</button>${settings.thesis_context_is_default ? '<span class="badge">Standardtext</span>' : '<span class="badge primary">angepasst</span>'}</div>
      </div>
      <div class="card stack sm">
        <h3>Export</h3>
        <div class="btn-row">
          <button class="btn" data-exp="xlsx">Literaturmatrix (Excel)</button><button class="btn" data-exp="csv">Literaturmatrix (CSV)</button>
          <button class="btn" data-exp="json">Alle Analysen (JSON)</button><button class="btn" data-exp="docx">Kapitelnotizen (Word)</button>
          <button class="btn" data-exp="bibtex">Bibliografie (BibTeX)</button><button class="btn" data-exp="ris">Bibliografie (RIS)</button>
        </div>
        <p class="xs muted">Bibliografische Metadaten werden automatisch extrahiert – vor Verwendung im Literaturverzeichnis prüfen.</p>
      </div>
      <div class="card stack sm">
        <h3>Backup & Wiederherstellung</h3>
        <div class="btn-row"><button class="btn primary" id="s-backup">Backup erstellen & herunterladen</button>
          <label class="btn">Backup wiederherstellen<input type="file" id="s-restore" accept=".zip" hidden></label></div>
        <p class="xs muted">Backup = Datenbank (Analysen, Notizen, Markierungen) + alle PDFs als ZIP. Vor einer Wiederherstellung wird automatisch ein Backup des aktuellen Stands angelegt.</p>
        ${backups.length ? `<div class="small"><b>Vorhandene Backups im Datenordner:</b><ul style="margin:4px 0 0;padding-left:18px">${backups.slice(0, 6).map((b) => `<li>${esc(b.name)} <span class="muted">(${(b.size / 1048576).toFixed(1)} MB)</span></li>`).join("")}</ul></div>` : ""}
      </div>
      <div class="card stack sm" style="grid-column:1/-1">
        <h3>Verarbeitungsstatus</h3>
        ${state.studies.length ? `<div class="table-wrap" style="max-height:320px"><table class="table"><thead><tr><th>Datei</th><th>Status</th><th>Meldung</th></tr></thead><tbody>
          ${state.studies.map((s) => `<tr><td class="clip"><a href="#/study/${s.id}">${esc(s.filename)}</a></td><td>${statusBadge(s.status)}</td><td class="small clip">${esc(s.status_message || "")}</td></tr>`).join("")}</tbody></table></div>` : '<div class="muted small">Keine Studien.</div>'}
      </div>
    </div>`;

  view.querySelector("#s-test").addEventListener("click", async (e) => {
    e.target.disabled = true;
    const out = view.querySelector("#s-test-out");
    out.innerHTML = '<span class="spinner"></span> Teste …';
    try { const r = await api.post("/api/test-ai"); out.innerHTML = `<span class="badge ok">OK</span> Modell ${esc(r.model)} antwortet.`; } catch (err) { out.innerHTML = `<span class="badge err">Fehler</span> ${esc(err.message)}`; }
    e.target.disabled = false;
  });
  const queue = async (all) => {
    if (all && !confirm("Alle Studien erneut analysieren? Das verursacht API-Kosten und ersetzt bestehende KI-Analysen (Notizen/Markierungen bleiben).")) return;
    try { const r = await api.post(`/api/studies/analyze-pending?include_analyzed=${all}`); toast(`${r.queued.length} Analyse(n) gestartet.`); await refreshStudies(); startPolling(); } catch (err) { toast(err.message, "err"); }
  };
  view.querySelector("#s-pending").addEventListener("click", () => queue(false));
  view.querySelector("#s-all").addEventListener("click", () => queue(true));
  view.querySelector("#s-ctx-save").addEventListener("click", async () => {
    try { await api.put("/api/settings", { thesis_context: view.querySelector("#s-ctx").value }); toast("Kontext gespeichert."); renderSettings(view, ctx); } catch (err) { toast(err.message, "err"); }
  });
  view.querySelector("#s-ctx-reset").addEventListener("click", async () => {
    try { await api.put("/api/settings", { thesis_context: "" }); toast("Standardtext wiederhergestellt."); renderSettings(view, ctx); } catch (err) { toast(err.message, "err"); }
  });
  view.querySelectorAll("[data-exp]").forEach((b) => b.addEventListener("click", async () => {
    b.disabled = true;
    try { await api.download(`/api/export/${b.dataset.exp}`); } catch (err) { toast(err.message, "err"); }
    b.disabled = false;
  }));
  view.querySelector("#s-backup").addEventListener("click", async (e) => {
    e.target.disabled = true;
    try { await api.download("/api/backup", "POST"); toast("Backup erstellt."); } catch (err) { toast(err.message, "err"); }
    e.target.disabled = false;
  });
  view.querySelector("#s-restore").addEventListener("change", async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    if (!confirm(`Backup „${f.name}“ wiederherstellen? Der aktuelle Stand wird ersetzt (vorher automatisch gesichert).`)) { e.target.value = ""; return; }
    try { const r = await api.uploadRaw("/api/restore", f); toast(`${r.restored_studies} Studien wiederhergestellt.`); await refreshStudies(); renderSettings(view, ctx); } catch (err) { toast(err.message, "err"); }
  });
}
