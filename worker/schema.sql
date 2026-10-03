-- 網頁單則評分；collect 以 id 遞增拉取（after=<最後 id>）
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  received_at TEXT NOT NULL,
  date TEXT NOT NULL,
  ref TEXT NOT NULL,
  value INTEGER NOT NULL
);
