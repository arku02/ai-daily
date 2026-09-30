# 審查紀錄

## 結構化審查
```json
{
  "mode": "full",
  "decision": "ready",
  "reviewer": "Claude Opus 5.5：提案、規格、設計與任務交叉審查",
  "rationale": "範圍對應使用者 2026-09-30 確認的第 2 步（AI 篩選與摘要），網頁、推送、回饋排序、排程列為非目標。R1 候選排序對齊 source-fetch 的 metrics 欄位，缺成長量時退回總數；R2 驗證規則讓無效 LLM 回應不會污染輸出；R4 規定連結只能來自原始資料並有逐項降級，避免編造連結與整天失敗；R5 以模型備援因應免費上限未知，缺 key 在呼叫前失敗並遮蔽 key；R7 讓使用者背景不進公開 repo，與使用者要求回饋私有的精神一致。每天約 6 次呼叫的估計寫在設計假設。每項需求與 D1 都有任務與測試對應。無待決業務問題。",
  "openQuestions": [],
  "coverage": [
    { "requirement": "R1", "task": "1.1", "test": "tests/test_digest.py" },
    { "requirement": "R2", "task": "1.2", "test": "tests/test_digest.py" },
    { "requirement": "R3", "task": "1.3", "test": "tests/test_digest.py" },
    { "requirement": "R4", "task": "1.4", "test": "tests/test_digest.py" },
    { "requirement": "R5", "task": "1.5", "test": "tests/test_digest.py" },
    { "requirement": "R6", "task": "1.6", "test": "tests/test_digest.py" },
    { "requirement": "R7", "task": "1.7", "test": "tests/test_digest.py" },
    { "requirement": "D1", "task": "1.8", "test": "tests/test_digest.py" }
  ]
}
```

## 檢查內容
- 需求來源：使用者 2026-09-30 的回饋（深度與應用建議正確、今天試一個挑容易上手的、以免費為主、排除融資與人事新聞）。
- 設計區分已知事實（實際 API 回應、定價頁內容）、假設（免費上限、JSON 模式）與方案。
- 不需要 ADR；取捨記在 design.md。
- 實作中的調整（規格已同步）：實跑發現同一事件被重複選入（OpenAI Dots 的 RSS 與 HN），加強選題規則 2 的「同一件事」定義後消失。今天試一個原本單一候選，模型對 PageIndex 回傳 skip（範例只支援 OpenAI key），改為最多 3 個依序候選、skip 就換下一個；並讓今天試一個候選取 8000 字 README，避免安裝步驟被截斷。profile 範例補上「可用 API：Gemini 免費、Ollama」。
- 手動實機確認（非自動測試）：2026-09-30 以使用者的 Gemini 免費 key、當天原始資料實跑 5 次，皆以 gemini-3.8-flash 完成，每次 6～7 次呼叫、約 80 秒，降級 0 則。最後一次：深度 15 則、快速瀏覽 15 則；今天試一個跳過 PageIndex 後選 Hindsight，其安裝指令 pip install hindsight-all -U、retain()／recall() 與 Gemini/Ollama 支援已對照原始 README 確認存在；「Windows 可直接跑」是模型推論，README 未明寫。連結全部來自原始資料。openai.com 的原文補充抓取回應 403，如預期改用原始摘要。

## 實際驗證
尚未執行。執行 verify 後讀取 .workflow/evidence/add-llm-digest.json 與對應測試輸出。
