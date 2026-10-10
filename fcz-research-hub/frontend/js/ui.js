// UI-Helfer: Escaping, Badges, Claims mit Quellenverweis, Modals, Toasts.
import { state } from "./state.js";

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export function html(strings, ...vals) {
  return strings.reduce((acc, s, i) => acc + s + (i < vals.length ? (vals[i] ?? "") : ""), "");
}

export function h(tag, attrs = {}, inner = "") {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null && v !== false) el.setAttribute(k, v === true ? "" : v);
  }
  if (typeof inner === "string") el.innerHTML = inner; else if (inner) el.append(inner);
  return el;
}

export const ICON = {
  page: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/></svg>',
  info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v5h1"/></svg>',
  warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></svg>',
  spark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8"/></svg>',
  close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg>',
  upload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 16V4M7 9l5-5 5 5M4 20h16"/></svg>',
  ext: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>',
};

export const STATUS_LABEL = {
  extracted: ["Text extrahiert", "info"],
  queued: ["In Warteschlange", "info"],
  analyzing: ["Analyse läuft", "info"],
  analyzed: ["Analysiert", "ok"],
  error: ["Fehler", "err"],
  needs_ocr: ["OCR nötig", "warn"],
  no_api: ["KI ausstehend", "warn"],
};

export function statusBadge(status) {
  const [label, cls] = STATUS_LABEL[status] || [status, ""];
  const spin = status === "analyzing" || status === "queued" ? '<span class="spinner" style="width:10px;height:10px;border-width:2px"></span>' : "";
  return `<span class="badge ${cls}">${spin}${esc(label)}</span>`;
}

const CLAIM_STATUS = {
  verified: ["verifiziert", "ok", "Angabe mit wörtlichem Zitat im PDF belegt."],
  uncertain: ["unsicher", "warn", "Angabe unsicher oder Zitat nicht exakt gefunden – im PDF prüfen."],
  not_reported: ["nicht berichtet", "", "Im Dokument nicht berichtet bzw. nicht ersichtlich."],
};
const SOURCE = {
  author_statement: ["Autoren", "primary", "Aussage/Angabe der Autoren"],
  ai_summary: ["KI-Zusammenfassung", "ai", "Zusammenfassende Formulierung der KI"],
  ai_assessment: ["KI-Bewertung", "ai", "Methodische Bewertung durch die KI"],
};

export function claimStatusBadge(status) {
  const [l, c, t] = CLAIM_STATUS[status] || [status, "", ""];
  return `<span class="badge ${c}" title="${esc(t)}">${esc(l)}</span>`;
}
export function sourceBadge(st) {
  const [l, c, t] = SOURCE[st] || [st, "", ""];
  return `<span class="badge ${c}" title="${esc(t)}">${esc(l)}</span>`;
}

export function pageLink(page, label, quote, studyId) {
  if (!page) return "";
  const lbl = label ? ` · gedr. ${esc(label)}` : "";
  return `<button class="page-link" data-goto-page="${page}" data-quote="${esc(quote || "")}" ${studyId ? `data-study="${studyId}"` : ""} title="Zur PDF-Seite springen (physische Seite ${page}${label ? `, gedruckte Seite ${esc(label)}` : ""})">${ICON.page}PDF-S. ${page}${lbl}</button>`;
}

const QC_LABEL = { exact: "Zitat wörtlich gefunden", fuzzy: "Zitat nahezu wörtlich gefunden", not_found: "Zitat nicht gefunden", no_quote: "", too_short: "Zitat zu kurz" };

export function claim(c, { studyId } = {}) {
  if (!c || typeof c !== "object") return '<span class="muted">—</span>';
  const nr = c.status === "not_reported";
  const qc = c.check?.quote_check;
  const qcBadge = qc === "exact" ? `<span class="badge ok" title="${QC_LABEL.exact}">✓ Zitat</span>`
    : qc === "fuzzy" ? `<span class="badge info" title="${QC_LABEL.fuzzy} (Abdeckung ${Math.round((c.check.coverage || 0) * 100)} %)">≈ Zitat</span>`
    : qc === "not_found" ? `<span class="badge err" title="${QC_LABEL.not_found}">✗ Zitat</span>` : "";
  const corrected = c.check?.page_corrected_from ? `<span class="xs muted" title="Die KI hatte Seite ${c.check.page_corrected_from} angegeben; das Zitat wurde auf Seite ${c.page} gefunden.">(Seite korrigiert)</span>` : "";
  return `<div class="claim">
    <div class="val ${nr ? "nr" : ""}">${esc(c.value)}</div>
    <div class="cmeta">${claimStatusBadge(c.status)}${nr ? "" : sourceBadge(c.source_type)}${qcBadge}${pageLink(c.page, c.page_label, c.quote, studyId)}${corrected}
    ${c.quote ? `<details class="quote"><summary>Originaltext anzeigen</summary><blockquote>„${esc(c.quote)}“</blockquote></details>` : ""}</div>
    ${c.check?.note && c.check.note !== "Demo-Daten" && !nr ? `<div class="check-note">${esc(c.check.note)}</div>` : ""}
  </div>`;
}

export function claims(list, opts) {
  const arr = (list || []).filter(Boolean);
  if (!arr.length) return '<div class="claim"><div class="val nr">Nicht berichtet</div></div>';
  return arr.map((c) => claim(c, opts)).join("");
}

export function kv(rows) {
  return `<div class="kv">${rows.map(([k, v]) => `<div class="k">${esc(k)}</div><div class="v">${v}</div>`).join("")}</div>`;
}

export function scoreView(score) {
  if (score === null || score === undefined) return '<span class="muted small">–</span>';
  const s = Math.round(score);
  return `<span class="score" title="Relevanz-Score (interne Passung, keine Qualitätsbewertung)"><span class="score-bar"><span style="width:${s}%"></span></span><span class="score-num">${s}</span></span>`;
}

export function toast(msg, type = "") {
  const t = h("div", { class: `toast ${type}` }, esc(msg));
  document.getElementById("toasts").append(t);
  setTimeout(() => t.remove(), type === "err" ? 7000 : 3800);
}

export function modal({ title, body, foot = "", wide = false, onClose }) {
  const bd = h("div", { class: "modal-backdrop" });
  bd.innerHTML = `<div class="modal" role="dialog" aria-modal="true" style="${wide ? "width:min(980px,100%)" : ""}">
    <div class="modal-head"><h2>${esc(title)}</h2><button class="btn icon ghost" data-close aria-label="Schließen">${ICON.close}</button></div>
    <div class="modal-body"></div>${foot ? `<div class="modal-foot">${foot}</div>` : ""}</div>`;
  const bodyEl = bd.querySelector(".modal-body");
  if (typeof body === "string") bodyEl.innerHTML = body; else bodyEl.append(body);
  const close = () => { bd.remove(); document.removeEventListener("keydown", onKey); onClose && onClose(); };
  const onKey = (e) => { if (e.key === "Escape") close(); };
  bd.addEventListener("click", (e) => { if (e.target === bd || e.target.closest("[data-close]")) close(); });
  document.addEventListener("keydown", onKey);
  document.body.append(bd);
  return { el: bd, body: bodyEl, close };
}

export function banner(type, htmlContent) {
  const icon = type === "warn" || type === "err" ? ICON.warn : ICON.info;
  return `<div class="banner ${type}">${icon}<div>${htmlContent}</div></div>`;
}

export function demoBanner() {
  return banner("demo", `<b>DEMO-Ansicht – fiktive Beispieldaten.</b> Es sind noch keine Studien importiert. Die angezeigten Einträge sind Platzhalter und enthalten keine wissenschaftlichen Aussagen. Importieren Sie Ihre PDFs über „PDFs importieren“.`);
}

export function label(group, key) {
  return state.vocab?.[group]?.[key] ?? key;
}

export function chapterTitle(key) {
  return state.vocab?.chapters?.find((c) => c.key === key)?.title ?? key;
}

export function debounce(fn, ms = 300) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

export function fmtDate(iso) {
  if (!iso) return "–";
  try { return new Date(iso).toLocaleString("de-CH", { dateStyle: "medium", timeStyle: "short" }); } catch (e) { return iso; }
}

export function aiOutputMeta(o) {
  return `<span class="badge ai">${ICON.spark.replace("<svg", '<svg style="width:12px;height:12px"')} KI-generiert</span><span class="xs muted">${esc(o.model || "")} · ${fmtDate(o.created_at)} · Basis: ${o.study_ids.length} Studie(n)${o.output?._citation_problems ? ` · <span style="color:var(--err)">${o.output._citation_problems} Belegproblem(e)</span>` : ""}</span>`;
}

const KIND = {
  literature_finding: ["Literaturbefund", "primary"],
  ai_synthesis: ["KI-Synthese", "ai"],
  recommendation: ["Eigene Empfehlung (KI)", "warn"],
};

export function citedItem(it) {
  const [kl, kc] = KIND[it.kind] || [it.kind, ""];
  const cites = (it.citations || []).map((c) => {
    const cls = c.check === "invalid_study" || c.check === "invalid_page" ? "bad" : (c.check === "page_exists" || c.check === "no_page") ? "weak" : "";
    const title = { matches_evidence: "Seite deckt sich mit belegter Angabe der Analyse", page_exists: "Seite existiert, aber ohne direkt verknüpften Beleg – prüfen", no_page: "ohne Seitenangabe", invalid_page: "Seite existiert nicht", invalid_study: "Studie nicht in der Auswahl – Beleg ungültig" }[c.check] || "";
    const pg = c.page ? `, S. ${c.page}${c.page_label ? ` (gedr. ${esc(c.page_label)})` : ""}` : "";
    return `<button class="cite ${cls}" data-cite-study="${c.study_id}" data-cite-page="${c.page || ""}" title="${esc(title)}">${esc(c.ref || c.study_id)}${pg}</button>`;
  }).join("");
  return `<div class="ai-item"><div>${esc(it.text)}</div><div class="row" style="gap:4px;margin-top:4px"><span class="badge ${kc}">${kl}</span>${cites}${it.unsupported ? '<span class="badge err">ohne Beleg</span>' : ""}</div></div>`;
}

export function citedList(items, emptyText = "Keine Einträge.") {
  if (!items || !items.length) return `<div class="muted small">${esc(emptyText)}</div>`;
  return items.map(citedItem).join("");
}

// Globale Delegation: Zitations-Chips öffnen die Studie auf der Seite
document.addEventListener("click", (e) => {
  const c = e.target.closest("[data-cite-study]");
  if (c) {
    const id = c.dataset.citeStudy; const p = c.dataset.citePage;
    location.hash = `#/study/${id}${p ? `?page=${p}` : ""}`;
  }
});
