# AI Company Meeting Protocol

這份協議把「多 agent 開會」限制成可控、可驗證、可量化的流程，而不是讓多個 agent 自由聊天到 token overflow 或無窮 loop。

## 目標

正式派工前，先由一場 bounded multi-agent meeting 產出：

- meeting minutes
- discussion transcript
- task list
- owner assignment
- acceptance criteria
- fallback plan
- stop conditions

## 角色

- `meeting_coordinator`
  - 控制議程、回合數、結束條件
  - 防止會議失焦
- `planner_agent`
  - 根據 `plan.json` / `jobs/*.json` 提出初版任務分派
- `risk_reviewer`
  - 專看 token overflow、scope 過大、重複提案、依賴衝突、歷史失敗訊號
- `decision_agent`
  - 收斂最終結論，決定是否可派工或必須 replan
- `reviewer_worker`
  - 執行後獨立驗收，不參與最初會議決策

## 回合規則

- 預設最多 `3` 輪
- 每輪固定順序：
  1. `meeting_coordinator`
  2. `planner_agent`
  3. `risk_reviewer`
  4. `decision_agent`
- 每輪都必須產生結構化發言：
  - `summary`
  - `proposed_actions`
  - `risk_flags`
  - `decision_state`

## 防 loop 規則

- 若同一版 task proposal digest 在後續輪次重複出現，標記 `proposal_repeat_detected`
- 若到 round limit 仍有：
  - `scope_too_broad`
  - `empty_scope`
  - repeated proposal
  則結論必須改成 `MEETING_NEEDS_REPLAN`
- 不允許會議無上限追加輪次

## 輸出 Schema

會議輸出必須符合 `configs/ai_company/meeting_decision.schema.json`，至少包含：

- `meeting_id`
- `meeting_status`
- `goal`
- `meeting_minutes`
- `rounds_used`
- `round_limit`
- `discussion_log`
- `task_assignments`
- `open_risks`
- `stop_conditions`

## Task Assignment 規範

每個 task 必須有：

- `task_id`
- `owner_role`
- `scope`
- `depends_on`
- `acceptance_criteria`
- `fallback_plan`

每個 task 的 `scope` 最多 `3` 個檔案。

## KPI

- `meeting_plan_valid_rate`
  - meeting 輸出符合 schema 的比例
- `meeting_minutes_presence_rate`
  - 每次會議都有 minutes 的比例
- `discussion_log_coverage_rate`
  - 每次會議都有完整 transcript 的比例
- `task_assignment_clarity_rate`
  - 每個 task 都有 owner/scope/acceptance/fallback 的比例
- `bounded_task_rate`
  - task scope 都在限制內的比例
- `meeting_convergence_rate`
  - meeting 能在 round limit 內收斂的比例
- `loop_guard_effectiveness_rate`
  - 遇到 repeated proposal 或 unresolved risk 時，會議能停止並回 `MEETING_NEEDS_REPLAN` 的比例
- `meeting_to_execution_success_rate`
  - 會議完成後，執行與 reviewer 驗收能成功銜接的比例

## 達標門檻

- meeting plan valid rate `= 100%`
- meeting minutes presence rate `= 100%`
- discussion log coverage rate `= 100%`
- task assignment clarity rate `= 100%`
- bounded task rate `>= 90%`
- meeting convergence rate `>= 90%`
- loop guard effectiveness rate `= 100%`
