// 測試用：以記憶體 D1、假的次數上限與網頁執行 worker/src/index.js，不連網。
// stdin：{env, now, limit, pages: {"<日期>": "<html>" 或狀態碼}, rows, requests: [{method, path, headers, body}]}
// stdout：{responses: [{status, headers, body}], rows, fetched}
import worker from "../src/index.js";

class FakeD1 {
  constructor(rows) {
    this.rows = rows.map((r) => ({ ...r }));
    this.nextId = Math.max(0, ...this.rows.map((r) => r.id)) + 1;
  }
  prepare(sql) {
    const db = this;
    return {
      bind(...args) {
        return {
          async run() {
            if (!sql.startsWith("INSERT INTO feedback")) throw new Error(`unexpected sql ${sql}`);
            const [received_at, date, ref, value] = args;
            db.rows.push({ id: db.nextId++, received_at, date, ref, value });
            return { success: true };
          },
          async all() {
            if (!sql.startsWith("SELECT")) throw new Error(`unexpected sql ${sql}`);
            const [after, limit] = args;
            return { results: db.rows.filter((r) => r.id > after).sort((a, b) => a.id - b.id).slice(0, limit) };
          },
        };
      },
    };
  }
}

class FakeLimiter {
  constructor(limit) {
    this.limit_ = limit;
    this.counts = new Map();
  }
  async limit({ key }) {
    const n = (this.counts.get(key) || 0) + 1;
    this.counts.set(key, n);
    return { success: n <= this.limit_ };
  }
}

const input = JSON.parse(await new Promise((resolve) => {
  let data = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (c) => (data += c));
  process.stdin.on("end", () => resolve(data));
}));

const fetched = [];
globalThis.fetch = async (url) => {
  fetched.push(String(url));
  const day = String(url).match(/(\d{4}-\d{2}-\d{2})\.html$/)?.[1];
  const page = input.pages?.[day];
  if (page === undefined) return new Response("not found", { status: 404 });
  if (typeof page === "number") return new Response("error", { status: page });
  return new Response(page, { status: 200 });
};

const db = new FakeD1(input.rows || []);
const env = { ...input.env, DB: db };
if (input.limit) env.LIMITER = new FakeLimiter(input.limit);
const now = Date.parse(input.now || "2026-09-30T01:00:00Z");

const responses = [];
for (const r of input.requests) {
  const init = { method: r.method || "GET", headers: { "CF-Connecting-IP": "1.2.3.4", ...(r.headers || {}) } };
  if (r.body !== undefined) init.body = typeof r.body === "string" ? r.body : JSON.stringify(r.body);
  const resp = await worker.fetch(new Request(`https://fb.example.workers.dev${r.path}`, init), env, {}, now);
  const text = await resp.text();
  responses.push({ status: resp.status, headers: Object.fromEntries(resp.headers), body: text ? JSON.parse(text) : null });
}
process.stdout.write(JSON.stringify({ responses, rows: db.rows, fetched }));
