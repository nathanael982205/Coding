// PDF-Viewer auf Basis von PDF.js (lokal gebündelt) mit Seitennavigation,
// Volltextsuche (Backend) und Markierung von Textpassagen (Koordinaten via PyMuPDF).
import { api } from "./api.js";
import { esc, debounce } from "./ui.js";

if (window.pdfjsLib) window.pdfjsLib.GlobalWorkerOptions.workerSrc = "vendor/pdf.worker.min.js";

export class PdfViewer {
  constructor(container, { studyId, pages = [] }) {
    this.studyId = studyId;
    this.pageMeta = Object.fromEntries(pages.map((p) => [p.page_number, p]));
    this.page = 1;
    this.scale = null; // null = Seitenbreite
    this.renderTask = null;
    this.highlightQuery = "";
    container.innerHTML = `
      <div class="pdf-toolbar">
        <button class="btn sm icon" data-a="prev" title="Vorherige Seite">‹</button>
        <span class="pg"><input class="input" data-a="page" type="number" min="1" value="1"> / <span data-a="total">–</span></span>
        <button class="btn sm icon" data-a="next" title="Nächste Seite">›</button>
        <span class="xs muted" data-a="label"></span>
        <span class="spacer"></span>
        <button class="btn sm icon" data-a="zoomout" title="Verkleinern">−</button>
        <button class="btn sm" data-a="fit" title="Seitenbreite">Breite</button>
        <button class="btn sm icon" data-a="zoomin" title="Vergrößern">+</button>
        <a class="btn sm" href="/api/studies/${studyId}/pdf" target="_blank" rel="noopener" title="PDF in neuem Tab öffnen">↗</a>
        <div class="pdf-search" style="flex-basis:100%"><input class="input" data-a="search" type="search" placeholder="Im PDF suchen …"></div>
      </div>
      <div class="pdf-results hidden" data-a="results"></div>
      <div class="pdf-canvas-wrap" data-a="wrap"><div class="pdf-page" data-a="pagebox"><canvas></canvas></div></div>
      <div class="pdf-status" data-a="status">PDF wird geladen …</div>`;
    this.$ = (a) => container.querySelector(`[data-a="${a}"]`);
    this.canvas = container.querySelector("canvas");
    this.$("prev").onclick = () => this.goto(this.page - 1);
    this.$("next").onclick = () => this.goto(this.page + 1);
    this.$("page").onchange = (e) => this.goto(+e.target.value);
    this.$("zoomin").onclick = () => { this.scale = (this.currentScale || 1) * 1.2; this.render(); };
    this.$("zoomout").onclick = () => { this.scale = Math.max(0.4, (this.currentScale || 1) / 1.2); this.render(); };
    this.$("fit").onclick = () => { this.scale = null; this.render(); };
    this.$("search").addEventListener("input", debounce((e) => this.search(e.target.value), 350));
    this.$("search").addEventListener("keydown", (e) => { if (e.key === "Escape") { e.target.value = ""; this.search(""); } });
    this.ro = new ResizeObserver(debounce(() => { if (this.scale === null) this.render(); }, 150));
    this.ro.observe(this.$("wrap"));
  }

  async load() {
    if (!window.pdfjsLib) { this.$("status").textContent = "PDF.js konnte nicht geladen werden."; return; }
    try {
      this.doc = await window.pdfjsLib.getDocument({ url: `/api/studies/${this.studyId}/pdf`, isEvalSupported: false }).promise;
      this.$("total").textContent = this.doc.numPages;
      this.$("page").max = this.doc.numPages;
      await this.render();
    } catch (e) {
      this.$("status").textContent = `PDF konnte nicht angezeigt werden: ${e.message}`;
    }
  }

  async goto(n, quote) {
    if (!this.doc) return;
    n = Math.max(1, Math.min(this.doc.numPages, n || 1));
    const changed = n !== this.page;
    this.page = n;
    this.highlightQuery = quote ?? (changed ? "" : this.highlightQuery);
    await this.render();
  }

  async render() {
    if (!this.doc) return;
    const page = await this.doc.getPage(this.page);
    const wrap = this.$("wrap");
    const base = page.getViewport({ scale: 1 });
    const fit = Math.max(0.3, (wrap.clientWidth - 30) / base.width);
    const scale = this.scale ?? fit;
    this.currentScale = scale;
    const vp = page.getViewport({ scale });
    const ratio = window.devicePixelRatio || 1;
    this.canvas.width = Math.floor(vp.width * ratio);
    this.canvas.height = Math.floor(vp.height * ratio);
    this.canvas.style.width = `${Math.floor(vp.width)}px`;
    this.canvas.style.height = `${Math.floor(vp.height)}px`;
    const box = this.$("pagebox");
    box.style.width = `${Math.floor(vp.width)}px`;
    box.style.height = `${Math.floor(vp.height)}px`;
    box.querySelectorAll(".pdf-hl").forEach((e) => e.remove());
    if (this.renderTask) { try { this.renderTask.cancel(); } catch (e) { /* ignore */ } }
    const ctx = this.canvas.getContext("2d");
    this.renderTask = page.render({ canvasContext: ctx, viewport: vp, transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : null });
    try { await this.renderTask.promise; } catch (e) { if (e?.name !== "RenderingCancelledException") throw e; return; }
    this.$("page").value = this.page;
    const meta = this.pageMeta[this.page] || {};
    this.$("label").textContent = meta.page_label ? `gedruckte S. ${meta.page_label}${meta.label_source === "heuristic" ? " (abgeleitet)" : ""}` : "";
    const qual = { scanned: "Seite ohne auslesbaren Text (Scan/Bild) – OCR erforderlich", empty: "Seite ohne Text", low_text: "wenig Text (z. B. Abbildung)", garbled: "Text nicht korrekt auslesbar" }[meta.quality];
    let status = `Physische PDF-Seite ${this.page} von ${this.doc.numPages}${qual ? ` · ⚠ ${qual}` : ""}`;
    if (this.highlightQuery) {
      const n = await this.highlight(this.highlightQuery, base);
      status += n ? ` · ${n} Markierung(en)` : " · Textstelle konnte nicht exakt markiert werden (Zitat ggf. über Zeilen/Spalten verteilt)";
    }
    this.$("status").textContent = status;
  }

  async highlight(q, base) {
    try {
      const r = await api.get(`/api/studies/${this.studyId}/highlight?page=${this.page}&q=${encodeURIComponent(q)}`);
      const box = this.$("pagebox");
      const sx = parseFloat(box.style.width) / (r.width || base.width);
      const sy = parseFloat(box.style.height) / (r.height || base.height);
      r.rects.forEach(([x0, y0, x1, y1], i) => {
        const d = document.createElement("div");
        d.className = "pdf-hl";
        Object.assign(d.style, { left: `${x0 * sx}px`, top: `${y0 * sy}px`, width: `${(x1 - x0) * sx}px`, height: `${(y1 - y0) * sy}px` });
        box.append(d);
        if (i === 0) {
          const wrap = this.$("wrap");
          wrap.scrollTo({ top: Math.max(0, y0 * sy - 80), behavior: "smooth" });
        }
      });
      return r.rects.length;
    } catch (e) { return 0; }
  }

  async search(q) {
    const res = this.$("results");
    if (!q || q.length < 2) { res.classList.add("hidden"); res.innerHTML = ""; return; }
    const hits = await api.get(`/api/studies/${this.studyId}/search?q=${encodeURIComponent(q)}`);
    res.classList.remove("hidden");
    if (!hits.length) { res.innerHTML = '<div class="small muted" style="padding:8px 12px">Keine Treffer im extrahierten Text.</div>'; return; }
    const rx = new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
    res.innerHTML = hits.map((h) => `<button data-p="${h.page}">S. ${h.page}${h.page_label ? ` (gedr. ${esc(h.page_label)})` : ""} · ${h.count}× — ${esc(h.snippet).replace(rx, (m) => `<mark class="q">${m}</mark>`)}</button>`).join("");
    res.querySelectorAll("button").forEach((b) => b.onclick = () => this.goto(+b.dataset.p, q));
    this.goto(hits[0].page, q);
  }

  destroy() { this.ro?.disconnect(); this.doc?.destroy(); }
}
