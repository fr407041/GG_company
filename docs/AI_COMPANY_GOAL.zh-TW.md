# AI Company Goal

目標是在 `Claude Code + Claude Code Router + open-source LLM` 的 Linux/Ubuntu 使用情境下，建立可公司導入的 `ai-company` 多代理協作流程。

## 核心目標

- 由 `master orchestrator` 接收任務
- 在正式派工前，先用 bounded multi-agent meeting 討論
- 會議必須產出：
  - meeting minutes
  - discussion transcript
  - task list
  - owner assignment
  - fallback / stop rules
- 各 agent 分工執行
- reviewer 最後獨立驗收
- 整體流程必須能防：
  - token overflow
  - infinite loop
  - silent fail
  - false success

## 角色定義

相容命名：

- Master orchestrator
- Planner worker
- Executor worker

- `master orchestrator`
  - 控制總流程、派工與回收
- `meeting_coordinator`
  - 控制會議議程、輪數與結束條件
- `planner_agent`
  - 依據 `plan.json` / `jobs/*.json` 提出任務切分
- `risk_reviewer`
  - 專看 overflow、scope 過大、重複提案、依賴衝突、歷史失敗訊號
- `decision_agent`
  - 收斂會議結論並輸出可派工 task assignments
- `research_agent`
  - 做資料蒐集、證據檢查、來源驗證
- `synthesis_agent`
  - 整理分析、結論、摘要
- `executor_backend`
  - 執行 backend / script / infra 類工作
- `executor_frontend`
  - 執行 frontend 類工作
- `executor_docs`
  - 執行文件與說明整理
- `reviewer_worker`
  - 驗收 raw/status/test artifacts，擋下 false success

## 狀態碼

- `SUCCESS`
- `PARTIAL_SUCCESS`
- `OVERFLOW_DETECTED`
- `EMPTY_RESPONSE`
- `MALFORMED_OUTPUT`
- `ROUTER_ERROR`
- `TIMEOUT`
- `DEPENDENCY_BLOCKED`
- `NEEDS_REPLAN`
- `CHILD_LIMIT_REACHED`
- `MAX_ATTEMPTS_REACHED`
- `FAILED`
- `MEETING_READY`
- `MEETING_NEEDS_REPLAN`
- `MEETING_CONTINUE`

## 驗證要求

- 每個 recovery / guard 都要可測
- task scope 必須 bounded
- meeting transcript 必須存在
- overflow / timeout / router / false success / loop 都要有防護
- 有量化 KPI 與 readiness gate
- 有 evaluator 與案例測試，不只文件敘述
