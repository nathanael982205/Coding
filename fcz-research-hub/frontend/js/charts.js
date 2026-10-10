// Chart.js-Helfer: einfarbige, ruhige Balkendiagramme mit Tooltips (Hell/Dunkel).
const charts = new Set();

function css(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function destroyCharts() {
  charts.forEach((c) => c.destroy());
  charts.clear();
}

export function barChart(canvas, labels, values, { horizontal = false, onClick, tooltipSuffix = "Studie(n)" } = {}) {
  if (!window.Chart) {
    canvas.parentElement.innerHTML = '<div class="muted small">Diagrammbibliothek nicht geladen.</div>';
    return null;
  }
  const primary = css("--primary");
  const grid = css("--border");
  const text = css("--text-2");
  const chart = new window.Chart(canvas, {
    type: "bar",
    data: { labels, datasets: [{ data: values, backgroundColor: primary, hoverBackgroundColor: css("--primary-hover"), borderRadius: 4, borderSkipped: "start", maxBarThickness: 34 }] },
    options: {
      indexAxis: horizontal ? "y" : "x",
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 250 },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: css("--surface"), titleColor: css("--text"), bodyColor: css("--text-2"),
          borderColor: css("--border-strong"), borderWidth: 1, padding: 10, displayColors: false,
          callbacks: { label: (ctx) => `${ctx.parsed[horizontal ? "x" : "y"]} ${tooltipSuffix}` },
        },
      },
      scales: {
        x: { grid: { display: horizontal, color: grid, drawTicks: false }, border: { display: false }, ticks: { color: text, precision: 0, font: { size: 11.5 } } },
        y: { grid: { display: !horizontal, color: grid, drawTicks: false }, border: { display: false }, ticks: { color: text, precision: 0, font: { size: 11.5 }, autoSkip: false } },
      },
      onClick: onClick ? (_e, els) => { if (els.length) onClick(labels[els[0].index], els[0].index); } : undefined,
      onHover: onClick ? (e, els) => { e.native.target.style.cursor = els.length ? "pointer" : "default"; } : undefined,
    },
  });
  charts.add(chart);
  return chart;
}

document.addEventListener("theme-changed", () => {
  // Diagramme werden beim nächsten Rendern mit neuen Farben erstellt
  window.dispatchEvent(new HashChangeEvent("hashchange"));
});
