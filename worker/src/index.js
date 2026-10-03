// R8：接收網頁上的單則評分，存進 D1；collect 以讀取金鑰拉回。
// 機密 WEB_KEY（瀏覽器的通行證，只能寫）、READ_KEY（collect 用，只能讀）以 wrangler secret 設定。

const DAY_RE = /^\d{4}-\d{2}-\d{2}$/;
const REF_RE = /^c\d{1,4}$/;
const MAX_BODY = 1024;
const PAGE_SIZE = 500;
const DAY_MS = 86400000;

function json(data, status, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...headers },
  });
}

function corsHeaders(env) {
  return {
    "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

// 固定時間比較，避免從回應時間猜出通行證
function sameSecret(given, expected) {
  if (typeof given !== "string" || typeof expected !== "string" || !expected) return false;
  const a = new TextEncoder().encode(given);
  const b = new TextEncoder().encode(expected);
  let diff = a.length ^ b.length;
  for (let i = 0; i < b.length; i++) diff |= (a[i] ?? 0) ^ b[i];
  return diff === 0;
}

function bearer(request) {
  const m = (request.headers.get("Authorization") || "").match(/^Bearer (.+)$/);
  return m ? m[1] : "";
}

function validDay(day, now) {
  if (!DAY_RE.test(day)) return false;
  const t = Date.parse(`${day}T00:00:00Z`);
  if (Number.isNaN(t) || new Date(t).toISOString().slice(0, 10) !== day) return false;
  const today = Date.parse(`${new Date(now).toISOString().slice(0, 10)}T00:00:00Z`);
  return t >= today - 60 * DAY_MS && t <= today + DAY_MS;
}

async function itemOnPage(env, day, ref) {
  let resp;
  try {
    resp = await fetch(`${env.SITE_URL}${day}.html`, { cf: { cacheTtl: 300, cacheEverything: true } });
  } catch {
    return null;
  }
  if (resp.status === 404) return false;
  if (!resp.ok) return null;
  return (await resp.text()).includes(`data-ref="${ref}"`);
}

async function post(request, env, cors, now) {
  if (env.LIMITER) {
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    const { success } = await env.LIMITER.limit({ key: ip });
    if (!success) return json({ error: "too many requests" }, 429, cors);
  }
  if (!sameSecret(bearer(request), env.WEB_KEY)) return json({ error: "unauthorized" }, 401, cors);
  const text = await request.text();
  if (new TextEncoder().encode(text).length > MAX_BODY) return json({ error: "too large" }, 413, cors);
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    return json({ error: "invalid json" }, 400, cors);
  }
  const { date, ref, value } = body || {};
  if (typeof date !== "string" || !validDay(date, now) || typeof ref !== "string" || !REF_RE.test(ref)
      || ![0, 1, 2].includes(value)) {
    return json({ error: "invalid feedback" }, 400, cors);
  }
  const found = await itemOnPage(env, date, ref);
  if (found === null) return json({ error: "site unavailable" }, 503, cors);
  if (!found) return json({ error: "unknown item" }, 404, cors);
  await env.DB.prepare("INSERT INTO feedback (received_at, date, ref, value) VALUES (?, ?, ?, ?)")
    .bind(new Date(now).toISOString().replace(/\.\d{3}Z$/, "Z"), date, ref, value)
    .run();
  return json({ ok: true }, 200, cors);
}

async function list(request, env, url) {
  if (!sameSecret(bearer(request), env.READ_KEY)) return json({ error: "unauthorized" }, 401);
  const after = Number.parseInt(url.searchParams.get("after") || "0", 10);
  const { results } = await env.DB
    .prepare("SELECT id, received_at, date, ref, value FROM feedback WHERE id > ? ORDER BY id LIMIT ?")
    .bind(Number.isFinite(after) && after > 0 ? after : 0, PAGE_SIZE)
    .all();
  return json({ items: results || [] }, 200);
}

export default {
  async fetch(request, env, ctx, now = Date.now()) {
    const url = new URL(request.url);
    const cors = corsHeaders(env);
    if (url.pathname !== "/feedback") return json({ error: "not found" }, 404);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (request.method === "POST") return post(request, env, cors, now);
    if (request.method === "GET") return list(request, env, url);
    return json({ error: "method not allowed" }, 405);
  },
};
