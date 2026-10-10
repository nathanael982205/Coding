// Schlanker API-Client. Der API-Schlüssel liegt ausschließlich im Backend.
async function request(method, url, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try { const j = await res.json(); if (j.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch (e) { /* ignore */ }
    throw new Error(detail);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res;
}

export const api = {
  get: (u) => request("GET", u),
  post: (u, b) => request("POST", u, b ?? {}),
  put: (u, b) => request("PUT", u, b),
  patch: (u, b) => request("PATCH", u, b),
  del: (u) => request("DELETE", u),

  // Upload einer Datei mit Fortschritt (XHR für upload.onprogress)
  upload(file, { analyze = true, onProgress } = {}) {
    return new Promise((resolve, reject) => {
      const fd = new FormData();
      fd.append("files", file, file.name);
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `/api/studies/upload?analyze=${analyze}`);
      xhr.upload.onprogress = (e) => { if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total); };
      xhr.onload = () => {
        try {
          const j = JSON.parse(xhr.responseText);
          if (xhr.status >= 400) reject(new Error(j.detail || xhr.statusText)); else resolve(j);
        } catch (e) { reject(new Error(`Upload fehlgeschlagen (${xhr.status})`)); }
      };
      xhr.onerror = () => reject(new Error("Netzwerkfehler beim Upload"));
      xhr.send(fd);
    });
  },

  async uploadRaw(url, file) {
    const fd = new FormData();
    fd.append("file", file, file.name);
    const res = await fetch(url, { method: "POST", body: fd });
    const j = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(j.detail || res.statusText);
    return j;
  },

  async download(url, method = "GET") {
    const res = await fetch(url, { method });
    if (!res.ok) {
      let msg = res.statusText;
      try { msg = (await res.json()).detail || msg; } catch (e) { /* ignore */ }
      throw new Error(msg);
    }
    const blob = await res.blob();
    const cd = res.headers.get("content-disposition") || "";
    const m = cd.match(/filename="?([^";]+)"?/);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = m ? m[1] : "export";
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  },
};
