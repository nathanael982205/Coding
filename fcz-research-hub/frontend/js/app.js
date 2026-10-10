// Einstiegspunkt: Router, globale Aktionen, Upload-Dialog, Status-Polling.
import { api } from "./api.js";
import { state, saveCompare } from "./state.js";
import { esc, modal, toast, ICON, statusBadge } from "./ui.js";
import { renderDashboard } from "./views/dashboard.js";
import { renderLibrary } from "./views/library.js";
import { renderMatrix } from "./views/matrix.js";
import { renderStudy } from "./views/study.js";
import { renderCompare } from "./views/compare.js";
import { renderTheory } from "./views/theory.js";
import { renderMethods } from "./views/methods.js";
import { renderGaps } from "./views/gaps.js";
import { renderSettings } from "./views/settings.js";

const ROUTES = {
  dashboard: renderDashboard,
  library: renderLibrary,
  matrix: renderMatrix,
  study: renderStudy,
  compare: renderCompare,
  theory: renderTheory,
  methods: renderMethods,
  gaps: renderGaps,
  settings: renderSettings,
};

const view = document.getElementById("view");
let renderToken = 0;

export async function refreshStudies() {
  state.studies = await api.get("/api/studies");
  document.getElementById("nav-count").textContent = state.studies.length || "";
  if (!state.studies.length && !state.demo) {
    try { state.demo = await api.get("/api/demo"); } catch (e) { /* ignore */ }
  }
  return state.studies;
}

export async function refreshStatus() {
  try {
    state.status = await api.get("/api/status");
    const pill = document.getElementById("ai-pill");
    pill.innerHTML = state.status.ai_configured
      ? `<span class="dot ok"></span>KI aktiv · ${esc(state.status.model)}`
      : '<span class="dot off"></span>KI nicht konfiguriert';
    pill.title = state.status.ai_configured ? "Claude API ist im Backend konfiguriert." : "ANTHROPIC_API_KEY in .env eintragen. Gespeicherte Analysen bleiben nutzbar.";
  } catch (e) { /* Backend offline */ }
}

function parseHash() {
  const raw = location.hash.replace(/^#\/?/, "") || "dashboard";
  const [path, query] = raw.split("?");
  const parts = path.split("/").filter(Boolean);
  const params = Object.fromEntries(new URLSearchParams(query || ""));
  return { route: parts[0] || "dashboard", args: parts.slice(1), params };
}

export async function route() {
  const { route: r, args, params } = parseHash();
  const fn = ROUTES[r] || renderDashboard;
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.route === r || (r === "study" && a.dataset.route === "library")));
  document.getElementById("sidebar").classList.remove("open");
  const token = ++renderToken;
  view.className = "view" + (r === "study" || r === "matrix" || r === "compare" ? " wide" : "");
  view.innerHTML = '<div class="empty"><span class="spinner"></span></div>';
  try {
    await fn(view, { args, params, isCurrent: () => token === renderToken });
  } catch (e) {
    console.error(e);
    if (token === renderToken) view.innerHTML = `<div class="banner err">${ICON.warn}<div><b>Fehler beim Laden.</b> ${esc(e.message)}<br><span class="small muted">Läuft das Backend? (python run.py)</span></div></div>`;
  }
  window.scrollTo(0, 0);
}

// ------------------------------------------------------------------ Upload-Dialog
export function openUpload() {
  const body = document.createElement("div");
  body.innerHTML = `
    <div class="dropzone" id="dz" tabindex="0">
      ${ICON.upload}
      <div style="font-weight:600;margin-top:8px">PDFs hierher ziehen oder klicken</div>
      <div class="small muted">Mehrere Dateien möglich · nur wissenschaftliche Studien (keine Spieler- oder Vereinsdaten)</div>
      <input type="file" id="file-input" accept="application/pdf,.pdf" multiple hidden>
    </div>
    <label class="check" style="margin-top:12px"><input type="checkbox" id="auto-analyze" ${state.status?.ai_configured ? "checked" : "disabled"}> Direkt mit KI analysieren ${state.status?.ai_configured ? "" : '<span class="badge warn">KI nicht konfiguriert</span>'}</label>
    <div class="upload-list" id="ul"></div>`;
  const m = modal({ title: "PDF-Studien importieren", body, foot: '<button class="btn" data-close>Schließen</button><a class="btn primary" href="#/library" data-close>Zur Bibliothek</a>', onClose: () => route() });
  const dz = body.querySelector("#dz");
  const input = body.querySelector("#file-input");
  const list = body.querySelector("#ul");
  dz.addEventListener("click", () => input.click());
  dz.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") input.click(); });
  dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("drag"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("drag"));
  dz.addEventListener("drop", (e) => { e.preventDefault(); dz.classList.remove("drag"); handle([...e.dataTransfer.files]); });
  input.addEventListener("change", () => { handle([...input.files]); input.value = ""; });

  async function handle(files) {
    const pdfs = files.filter((f) => f.name.toLowerCase().endsWith(".pdf") || f.type === "application/pdf");
    files.filter((f) => !pdfs.includes(f)).forEach((f) => toast(`Übersprungen (kein PDF): ${f.name}`, "err"));
    const analyze = body.querySelector("#auto-analyze").checked;
    const items = pdfs.map((f) => {
      const el = document.createElement("div");
      el.className = "upload-item";
      el.innerHTML = `<div class="row"><span class="name">${esc(f.name)}</span><span class="spacer"></span><span class="xs muted">${(f.size / 1048576).toFixed(1)} MB</span></div>
        <div class="progress"><span></span></div><div class="xs muted st" style="margin-top:4px">Wartet …</div>`;
      list.append(el);
      return { f, el };
    });
    for (const { f, el } of items) {
      const bar = el.querySelector(".progress > span");
      const st = el.querySelector(".st");
      st.textContent = "Wird hochgeladen …";
      try {
        const res = await api.upload(f, { analyze, onProgress: (p) => { bar.style.width = `${Math.round(p * 100)}%`; if (p >= 1) { st.textContent = "Textextraktion …"; el.querySelector(".progress").classList.add("indet"); } } });
        el.querySelector(".progress").classList.remove("indet");
        bar.style.width = "100%";
        const r = res.results[0];
        if (r.result === "imported") {
          const tq = r.text_quality || {};
          st.innerHTML = `${statusBadge(r.status)} <a href="#/study/${r.study_id}" data-close>öffnen</a> · ${tq.page_count} Seiten · ${esc(r.message || "")}`;
          if (r.status === "needs_ocr" || tq.overall === "partial" || r.possible_duplicate) bar.style.background = "var(--warn)";
        } else if (r.result === "duplicate") {
          bar.style.background = "var(--muted)";
          st.innerHTML = `<span class="badge">Dublette</span> ${esc(r.message)} <a href="#/study/${r.study_id}" data-close>öffnen</a>`;
        } else {
          bar.style.background = "var(--err)";
          st.innerHTML = `<span class="badge err">Fehler</span> ${esc(r.message)}`;
        }
      } catch (e) {
        bar.style.background = "var(--err)";
        st.innerHTML = `<span class="badge err">Fehler</span> ${esc(e.message)}`;
      }
    }
    await refreshStudies();
    startPolling();
  }
  return m;
}

// ------------------------------------------------------------------ Polling laufender Analysen
let pollTimer = null;
export function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(async () => {
    const before = new Map(state.studies.map((s) => [s.id, s.status]));
    try { await refreshStudies(); } catch (e) { return; }
    const busy = state.studies.some((s) => s.status === "queued" || s.status === "analyzing");
    const changed = state.studies.some((s) => before.get(s.id) !== s.status);
    if (changed) {
      state.studies.filter((s) => before.get(s.id) && before.get(s.id) !== s.status && (s.status === "analyzed" || s.status === "error"))
        .forEach((s) => toast(s.status === "analyzed" ? `Analyse fertig: ${s.title || s.filename}` : `Analyse fehlgeschlagen: ${s.filename}`, s.status === "error" ? "err" : ""));
      document.dispatchEvent(new CustomEvent("studies-changed"));
    }
    if (!busy) { clearInterval(pollTimer); pollTimer = null; }
  }, 4000);
}

// ------------------------------------------------------------------ Init
async function init() {
  document.getElementById("upload-btn").addEventListener("click", openUpload);
  document.getElementById("menu-btn").addEventListener("click", () => document.getElementById("sidebar").classList.toggle("open"));
  document.getElementById("theme-btn").addEventListener("click", () => {
    const root = document.documentElement;
    const isDark = root.dataset.theme === "dark" || (!root.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
    root.dataset.theme = isDark ? "light" : "dark";
    try { localStorage.setItem("rh-theme", root.dataset.theme); } catch (e) { /* ignore */ }
    document.dispatchEvent(new CustomEvent("theme-changed"));
  });
  const gs = document.getElementById("global-search");
  gs.addEventListener("keydown", (e) => {
    if (e.key === "Enter") location.hash = `#/library?q=${encodeURIComponent(gs.value.trim())}`;
  });
  document.addEventListener("studies-changed", () => {
    const { route: r } = parseHash();
    if (r === "dashboard") route();
  });
  saveCompare();
  try {
    const [vocab] = await Promise.all([api.get("/api/vocab"), refreshStatus(), refreshStudies()]);
    state.vocab = vocab;
  } catch (e) {
    view.innerHTML = `<div class="banner err">${ICON.warn}<div><b>Backend nicht erreichbar.</b> Bitte den Server starten: <code>python run.py</code> und die Seite unter http://localhost:8000 öffnen.<br><span class="small">${esc(e.message)}</span></div></div>`;
    return;
  }
  if (state.studies.some((s) => s.status === "queued" || s.status === "analyzing")) startPolling();
  window.addEventListener("hashchange", route);
  route();
}

init();
