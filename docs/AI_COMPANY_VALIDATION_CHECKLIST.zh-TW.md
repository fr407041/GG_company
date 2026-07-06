# AI Company Validation Checklist

這份清單用來驗證 `ai-company` 是否真的有效，而不是只看 demo 有沒有跑起來。

## 1. 架構可用性

- `master -> planner -> worker` 鏈路存在
- 所有 agent 都走 `Claude Code + router`
- 任務狀態可追蹤
- 有統一的 status contract

## 2. 任務拆解

- 高層任務會先切成 bounded tasks
- 每個 task scope 小而明確
- 不直接把整包大型專案全文送進單次 prompt
- 任務失敗後會縮 scope 而不是原樣重試

## 3. 執行品質

- worker 結果可驗證
- false success 會被擋下
- schema 與 artifact 可追蹤
- 變更結果與證據相互對應

## 4. 失敗恢復

- overflow 有 recovery
- timeout 有 recovery
- router empty / partial response 有 recovery 或 bounded stop
- needs-replan 會回到更小範圍
- repeated failure 會停，不無限 loop

## 5. Token / Context 控制

- 有 overflow guard
- 有 bounded retry
- 有短輸出 / signal-first 設計
- 有單檔或小範圍 fallback

## 6. 防卡死

- same-failure guard 存在
- replan-loop guard 存在
- child invocation cap 存在
- child cleanup 不會殺到 main orchestrator

## 7. 交付與審計

- raw output 保留
- status / summary / artifacts 保留
- 有 install / quickstart / company test matrix 文件
- 有 readiness / KPI evaluator

## KPI Gate

- scenario pass rate `>= 85%`
- critical guard coverage `= 100%`
- 歷史 readiness score `>= 90 / 100`
- failure-case library `>= 12` 個腳本
- 有至少 1 份非空 raw output 與 artifact bundle

## 這次 evaluator 的誠實限制

- 允許使用既有 `Claude + Router` 歷史 run artifacts 當證據
- 若本輪沒有新的 Linux live rerun，該項只能算 `partial`
- 不可把文件存在誤當成 live execution success
