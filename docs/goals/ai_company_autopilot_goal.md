# AI-company Autopilot Goal

## Objective
建立 AI-company orchestration core，讓任務建立後可自動完成 task classification、pipeline attach、meeting trigger、agent assignment、event logging 與 decision trace，並以單頁簡化 Web GUI 呈現 current status、active agents、result trustworthiness 與可展開細節。只有當 KPI spec、test matrix、SQLite-backed monitor、simple GUI 與 goal check 全部就位且驗證通過時，才視為完成。

## Layer 1: Core Build
- 任務進來後，自動分類 task type。
- 依 task type 自動掛上對應 pipeline。
- 在必要條件下自動觸發 bounded planning / replan meeting。
- 自動指派 agent 角色與 owner。
- 將 pipeline、meeting、decision、artifact、alert 寫入可追蹤事件流。
- 將結果同步進 SQLite-backed monitor，供簡單 GUI 顯示。

## Layer 2: Validation
- 以 test matrix 驗證常見成功路徑與真實失敗路徑。
- 至少覆蓋 overflow、router empty response、partial response、false success、replan loop 等風險。
- 以 KPI 規格量化 automation、stability、traceability、quality、usability。
- 只有 goal check 通過，才可視為可交付狀態。

## GUI Constraints
- 只保留三個主要畫面區塊：current status、active agents、result trustworthiness。
- 其他細節以展開方式呈現，不可把首頁做成過重的 control center。
- 介面目標是讓公司內部使用者快速判斷現在進度、誰在做、結果是否可信。

## Deliverables
- `configs/ai_company/*.autopilot.json`
- `scripts/check_ai_company_autopilot_goal.js`
- `.claude/goal/active-goal.json`
- `.claude/skills/research-task-orchestrator/*`
- `docs/common_research_orchestrator_zh-TW.md`
- `agent_os_mvp/backend/app/services/ai_company_monitor.py`
- `agent_os_mvp/frontend/src/App.jsx`
