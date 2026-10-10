// Gemeinsamer Anwendungszustand
function loadCompare() {
  try { return JSON.parse(localStorage.getItem("rh-compare") || "[]"); } catch (e) { return []; }
}

export const state = {
  vocab: null,
  status: null,
  studies: [],
  demo: null,
  compare: loadCompare(),
  libraryFilters: {},
  libraryView: (() => { try { return localStorage.getItem("rh-libview") || "cards"; } catch (e) { return "cards"; } })(),
};

export function saveCompare() {
  try { localStorage.setItem("rh-compare", JSON.stringify(state.compare)); } catch (e) { /* ignore */ }
  const el = document.getElementById("nav-cmp");
  if (el) el.textContent = state.compare.length ? state.compare.length : "";
}

export function toggleCompare(id) {
  id = Number(id);
  const i = state.compare.indexOf(id);
  if (i >= 0) state.compare.splice(i, 1);
  else {
    if (state.compare.length >= 5) return { ok: false, msg: "Maximal 5 Studien vergleichbar." };
    state.compare.push(id);
  }
  saveCompare();
  return { ok: true, on: i < 0 };
}
