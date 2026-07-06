# Common Research Orchestrator 與 Simple Web GUI

這套內容把已驗證可運作的 `ai-company / Claude + router` 工作流整理成公司可參考的低依賴方案。

核心不是做一個很多頁、很多名詞的 command center，而是遵循「大道至簡」：
- 先看現在有沒有正常前進
- 再看哪個 agent 正在做什麼
- 最後看結果可不可信

## 內容組成

### 1. ai-company orchestration skill

- Skill 路徑：`.claude/skills/research-task-orchestrator/`
- 用途：
  - 先做 bounded meeting
  - 再 dispatch 小 scope child job
  - 最後用 verifier + KPI 收斂結果

### 2. 通用 research spec 骨架

- Spec 範例：`docs/ai_specs/common-research-summary-example.json`
- Prep：`scripts/prepare_common_research_case.py`
- 驗證：`scripts/verify_common_research_artifact.py`
- Runner：`scripts/run_common_research_with_router.sh`
- Goal check：`scripts/check_common_research_goal.js`

### 2.5 自動化規則資產

- Event schema：`configs/ai_company/event_schema.autopilot.json`
- Pipeline rules：`configs/ai_company/pipeline_rules.autopilot.json`
- Meeting triggers：`configs/ai_company/meeting_triggers.autopilot.json`
- Agent assignment rules：`configs/ai_company/agent_assignment_rules.autopilot.json`

### 3. Simple Web GUI

- Backend：`agent_os_mvp/backend/`
- Frontend：`agent_os_mvp/frontend/`
- 特性：
  - 單頁
  - 低依賴
  - 使用既有 `sqlite3`
  - 預設只看三塊：現在狀態、誰在工作、結果可信嗎
  - prompt / raw output / exec log 都在展開細節裡

## 為何這版比較適合公司環境

- 不靠大型 dashboard framework
- 不引入新的資料庫，直接用 SQLite
- 不需要很多頁面才能知道現在有沒有卡住
- 可直接讀 `results/ai_company_task_harness`，並同步摘要進 SQLite
- 保留工程除錯能力，但預設不把人淹沒在細節裡

## 安裝方式

### 後端

需求：
- Python 3.10+
- 已安裝 `fastapi`、`uvicorn`、`pydantic`

安裝依賴：

```bash
cd agent_os_mvp/backend
pip install -r requirements.txt
```

啟動後端：

```bash
cd agent_os_mvp/backend
uvicorn app.main:app --reload
```

說明：
- SQLite 檔案預設使用 `agent_os_mvp/data/agent_os.db`
- 若要改路徑，可設定 `AGENT_OS_DB_PATH`
- ai-company run artifacts 會在 API 被呼叫時同步摘要進 SQLite

### 前端

需求：
- Node.js 18+
- npm

安裝依賴：

```bash
cd agent_os_mvp/frontend
npm install
```

啟動前端：

```bash
cd agent_os_mvp/frontend
npm run dev
```

建置：

```bash
cd agent_os_mvp/frontend
npm run build
```

## 使用方式

1. 先讓你的 ai-company run 產生在：

```text
results/ai_company_task_harness/
```

2. 啟動後端與前端。
3. 打開前端頁面後，預設會顯示最新 run。
4. 先只看三區：
   - `現在狀態`
   - `誰在工作`
   - `結果可信嗎`
5. 需要 deeper debug 時，再展開：
   - 會議與任務細節
   - prompt / raw output / exec log
   - 最近 run 清單

## Dashboard 資料來源

資料流程如下：

1. 讀取 `results/ai_company_task_harness` 的 run artifacts
2. 後端整理成單一 payload
3. 同步摘要進 SQLite table `ai_company_runs`
4. 前端再從後端 API 讀取

## API

- `GET /api/ai-company-monitor`
  - 回傳簡化總覽與最近 run
- `GET /api/ai-company-monitor/runs/{run_id}`
  - 回傳單一 run 詳細內容

## 建議使用原則

- 預設不要讓使用者先看到全部 meeting trace
- 預設不要把 raw log 直接鋪滿整頁
- 先看：
  - 是否成功
  - 是否有 overflow / router error / replan 壓力
  - active agent 還有誰沒收斂
- 只有需要 debug 時才進一步展開技術細節

## 測試案例設計原則

這份方案的測試案例不是只測 happy path，而是直接參考實際踩過的問題：

- token overflow
- router empty / partial response
- bounded replan
- false success without real file change
- reasoning-heavy output pressure

對應測試矩陣請看：

- `configs/ai_company/test_matrix.autopilot.json`
