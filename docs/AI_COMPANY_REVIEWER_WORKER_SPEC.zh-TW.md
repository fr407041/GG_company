# AI Company Reviewer Worker Spec

`reviewer_worker` 是獨立於 planner / executor 的角色，專門負責驗收與退回，不直接負責實作。

## 角色責任

- 驗證 executor 輸出是否符合 task assignment
- 驗證檔案變更是否真的發生
- 驗證 acceptance criteria 是否達成
- 擋下 false success
- 必要時要求 repair 或 replan

## Reviewer 輸入

- `task_assignment`
- `worker_status.json`
- `raw_output.txt`
- `before/after file hash`
- `test result`

## Reviewer 輸出 Schema

最終輸出必須符合 `configs/ai_company/reviewer_verdict.schema.json`：

- `task_id`
- `review_status`
- `owner_role`
- `verdict`
- `evidence`
- `repair_action`
- `replan_required`

## Reviewer verdict

- `ACCEPTED`
- `REPAIR_REQUIRED`
- `REPLAN_REQUIRED`
- `FALSE_SUCCESS_BLOCKED`
- `SCHEMA_INVALID`
- `MISSING_ARTIFACT`

## Reviewer 必檢項

- 是否真的改到指定 scope
- 是否有未授權擴散修改
- 是否測試或驗收條件失敗
- 是否只回自然語言卻沒改檔
- 是否 output 格式不合法

## 量化 KPI

- `reviewer_rejection_precision`
  - reviewer 擋下的壞結果中，真正有問題的比例
- `false_success_block_rate`
  - 假成功被擋下的覆蓋率
- `reviewer_artifact_coverage`
  - reviewer 是否檢到 raw/status/test/before-after 證據

## Ready 標準

- reviewer verdict schema 可驗證
- false success 有明確阻擋機制
- reviewer 不依賴人工閱讀才能下結論
