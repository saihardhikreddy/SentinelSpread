/* Thin client for the SentinelSpread FastAPI backend (served from the same origin). */

export class ApiError extends Error {
  constructor(message, { status = 0, data = null, raw = "" } = {}) {
    super(message);
    this.status = status;
    this.data = data;       // structured `detail` object when the API sent one
    this.raw = raw;         // the API's own wording, for the console
  }
}

const DECRYPT_PATH = /decrypt|extract|verify|receive/;
const CRYPTO_FAILURE = /padding|mac check|tag|decrypt|incorrect|authenticat|invalid (key|signature)|ciphertext|oaep|bad (key|magic)/i;

/** Turn an API failure into a sentence a person can act on. */
function friendly(path, status, detail) {
  if (detail && typeof detail === "object" && !Array.isArray(detail) && detail.message) return detail.message;
  if (Array.isArray(detail)) {          // FastAPI request validation
    const first = detail[0] || {};
    const field = (first.loc || []).filter((x) => x !== "body").join(" › ");
    return `Check the form${field ? `: “${field}”` : ""} ${first.msg || "has an invalid value"}.`;
  }
  const text = typeof detail === "string" ? detail : "";
  if (status === 404 && text) return text;
  if (status >= 500) return text && /\s/.test(text) && !/traceback|exception/i.test(text) ? text : "The server hit a problem handling that. Try again, and check the API log if it keeps happening.";
  if (DECRYPT_PATH.test(path) && (CRYPTO_FAILURE.test(text) || !/\s/.test(text))) {
    if (path.includes("audio")) return "Couldn’t read a message from this file: the password is wrong, or it carries no hidden message.";
    if (path.includes("stego") || path.includes("watermark")) return "Couldn’t read a message from this image: it may not contain one, or it was re-saved in a lossy format that erased it.";
    return "Couldn’t decrypt: the message was altered, or the wrong key or password was used.";
  }
  if (text && /\s/.test(text) && !/^['"{\[]/.test(text)) return text;       // already readable
  if (/key|pem/i.test(text)) return "That key isn’t valid. Paste a full PEM key including its BEGIN and END lines.";
  return "The server couldn’t process that input. Check the values and try again.";
}

async function parse(res, path = "") {
  if (res.ok) return res;
  let detail = null, raw = `${res.status} ${res.statusText}`;
  try {
    const body = await res.json();
    if (body && body.detail != null) { detail = body.detail; raw = typeof detail === "string" ? detail : JSON.stringify(detail); }
  } catch { /* non-JSON error body */ }
  console.debug("[api]", path, res.status, raw);
  throw new ApiError(friendly(path, res.status, detail), { status: res.status, data: detail && typeof detail === "object" && !Array.isArray(detail) ? detail : null, raw });
}

const offline = () => new ApiError("Can’t reach the SentinelSpread API. Check that the server is still running.", { status: 0 });
async function send(path, init) {
  try { return await fetch(path, init); } catch { throw offline(); }
}

export async function postJSON(path, body) {
  const res = await parse(await send(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }), path);
  return res.json();
}

export async function getJSON(path) {
  return (await parse(await send(path, { cache: "no-store" }), path)).json();
}

/** Multipart POST. Returns parsed JSON, or { blob, filename } for file responses. */
export async function postForm(path, fields) {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) fd.append(k, v);
  const res = await parse(await send(path, { method: "POST", body: fd }), path);
  const type = res.headers.get("Content-Type") || "";
  if (type.includes("application/json")) return res.json();
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return { blob: await res.blob(), filename: match ? match[1] : "download.bin" };
}

export async function health() {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 4000);
  try {
    const res = await fetch("/health", { signal: ctrl.signal, cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

export const fileToDataURL = (file) => new Promise((resolve, reject) => {
  const r = new FileReader();
  r.onload = () => resolve(r.result);
  r.onerror = () => reject(r.error);
  r.readAsDataURL(file);
});

export async function fileToBase64(file) {
  const url = await fileToDataURL(file);
  return url.slice(url.indexOf(",") + 1);
}
