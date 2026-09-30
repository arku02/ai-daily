## MODIFIED Requirements

### Requirement: R2 - Selection
digest SHALL 以一次 LLM 呼叫，依 profile 的背景、興趣與排除主題，從候選中選出 news、models、arch、github 四個章節的深度項目與快速瀏覽項目、三句「今天只看三件事」，以及至多 3 個依優先順序排列的「今天試一個」候選。程式 SHALL 驗證回應：不存在的代號與未知章節 SHALL 被丟棄；同一代號只保留第一次出現；每章節深度與快速瀏覽數量 SHALL 截斷到 digest.toml 的上限；今天試一個候選中不存在或重複的代號 SHALL 被丟棄。選題提示 SHALL 包含 profile 的排除主題、今天試一個的挑選規則，以及「每個章節深度至少 2 則」的要求。驗證後若有任何章節的深度項目為 0，digest SHALL 再呼叫一次選題並附上哪些章節是空的，採用兩次中空章節較少的結果（相同時採用深度項目總數較多者），並記錄警告。

#### Scenario: Invalid selections dropped
- **WHEN** LLM 回傳的 news 含 c3、c999、c3，另有未知章節 gossip
- **THEN** news 只含 c3，gossip 被丟棄

#### Scenario: Section cap
- **WHEN** news 深度上限為 5，LLM 選了 7 個有效代號
- **THEN** news 深度只保留前 5 個

#### Scenario: Exclusions in prompt
- **WHEN** profile 的排除主題為融資新聞與公司人事
- **THEN** 選題提示含這兩個主題

#### Scenario: Empty section reselected
- **WHEN** 第一次選題的 models 與 arch 深度項目都是 0，第二次四個章節都有項目
- **THEN** 採用第二次的結果，warnings 記錄重新選題，第二次的提示列出 models 與 arch
