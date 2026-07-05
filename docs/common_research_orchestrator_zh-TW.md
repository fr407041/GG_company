# Common Research Orchestrator 使用說明

這份最小包的目標，不是做一個很重的 AI-company 平台，而是提供一套能在 `claude + router` 或相近環境中落地的通用任務編排骨架。

## 核心能力
- 自動 task classification
- 自動 pipeline attach
- 必要時自動觸發 bounded meeting
- agent assignment 與 owner trace
- event log / decision trace
- simple web gui 顯示 current status、active agents、result trustworthiness
- SQLite 作為最小可攜狀態儲存

## 適合公司環境的原因
- 不強依賴大型額外框架。
- 配置集中在 `configs/ai_company/`，方便調參。
- skill 與 goal 放在 `.claude/`，便於 Claude Code 讀取。
- 首頁只看三件事：現在狀態、誰在工作、結果可信嗎。

## 目錄
- `agent_os_mvp/backend`：FastAPI + SQLite monitor API
- `agent_os_mvp/frontend`：簡單單頁看板
- `configs/ai_company`：KPI、test matrix、meeting/pipeline/agent 規則
- `.claude/skills/research-task-orchestrator`：Claude 可讀的 skill
- `docs/goals/ai_company_autopilot_goal.md`：本次目標定義
- `scripts/check_ai_company_autopilot_goal.js`：最小 goal checker

## Backend 啟動
```bash
cd agent_os_mvp/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Frontend 啟動
```bash
cd agent_os_mvp/frontend
npm install
npm run dev
```

預設前端會呼叫 `http://localhost:8000/api/ai-company-monitor`。

## API
- `GET /health`
- `GET /api/ai-company-monitor`
- `GET /api/ai-company-monitor/runs/{run_id}`

## Goal Check
```bash
node scripts/check_ai_company_autopilot_goal.js
```

通過後會輸出目前 KPI 類別數、test cases 數、pipelines 數與首頁三大區塊檢查結果。

## 設計原則
- 任務流程自動串起來，不要靠使用者手動指定每一步。
- meeting 要有收斂機制，不能無窮討論。
- 當 overflow、router empty/partial、false success 發生時，要有 bounded recovery，而不是卡死。
- 先求簡潔可讀，再逐步擴充。
