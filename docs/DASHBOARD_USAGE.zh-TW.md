# AI Company Dashboard 使用說明

這個 dashboard 是用來看 AI Company 任務執行情況的。

你不用先懂所有術語，只要照下面順序看，就能快速知道：

- 這次任務有沒有成功
- 哪一關卡住
- 失敗的任務有沒有被重跑
- 下一步應該看哪裡

## 1. 先看最上面的三個區塊

### Run Overview

這是本次 run 的總結。

重點看：

- `Healthy`：整體看起來正常。
- `Needs Attention`：有某些關卡需要注意，但不一定代表整個 run 失敗。
- `Blocked`：有明確問題，需要人工檢查。
- `Next`：dashboard 建議你下一步先看哪裡。

如果你第一次使用，先看這一塊就好。

### What Needs Attention

這是待處理清單，通常是最重要的區塊。

它會告訴你：

- 問題來源是哪裡，例如 `Agent`、`Watchdog`、`Output Guard`
- 問題大概是什麼
- 建議下一步要做什麼

如果這裡沒有嚴重項目，代表目前沒有明顯 blocker。

### Pipeline Timeline

這是 AI Company 的流程圖：

```text
Input Guard -> Meeting -> Execution -> Reviewer -> Output Guard -> Watchdog -> Contracts
```

每一關的狀態意思：

- `Pass`：這關通過。
- `Warning`：有訊號要注意，但不一定失敗。
- `Fail`：這關有問題。
- `Not Run`：還沒有資料，或這關還沒跑。

## 2. 下方分頁怎麼看

### Overview

看總體數字和最後輸出摘要。

### Agents

看每個 agent 或 task 的狀態。

常見狀態：

- `Running`：正在跑。
- `Waiting`：等前一個任務或 reviewer。
- `Done`：完成。
- `Failed`：任務出問題。
- `Idle`：這次 run 沒有用到這個角色。

如果想知道哪個任務 fail，先看這個分頁。

### Guards

看安全檢查、格式檢查、輸入輸出檢查。

這裡會顯示：

- `Input Guard`：使用者輸入或任務 spec 是否安全。
- `Output Guard`：AI 輸出是否符合規則。
- `Contracts`：產物格式是否符合 schema。
- `Failure families`：失敗類型統計。

如果 dashboard 顯示 `Blocked` 或 `Needs Attention`，通常要來這裡看原因。

### Artifacts

看輸出產物和證據。

這裡會顯示：

- artifact checks
- summary
- claims
- evidence refs
- status artifacts

如果你想確認「AI 說它完成了，有沒有證據」，看這裡。

### Runs

切換歷史 run。

### Debug

給熟手或除錯用。

這裡會看到：

- watchdog 詳細狀態
- agent reliability
- guard JSON
- prompt
- raw output
- execution log

一般使用者不需要一開始看這裡。

## 3. Fail 會不會自動重跑？

會，但不是無限重跑。

流程大概是：

1. worker 執行任務。
2. reviewer 檢查結果。
3. 如果 reviewer 發現問題，例如 `NEEDS_REPLAN`、缺證據、格式錯誤，系統會產生 reassignment。
4. reassignment 會縮小任務範圍再跑一次。
5. 如果重跑後成功，整個 run 仍然可以是 `pass`。
6. 如果重跑後還是不行，就會被 watchdog 或 failure family 標出來。

預設每個 run 的 reassignment 次數有限，避免一直重跑同一個錯誤。

## 4. Demo case 怎麼看

常用 demo：

```text
general-task-mock-replan
```

這個 demo 故意讓其中一個任務先出現 `NEEDS_REPLAN`。

你會看到：

- 有任務一開始需要 replan
- reviewer 會發現這件事
- 系統會產生縮小範圍後的 reassignment
- 重跑後整體 run 仍然可以 pass

這個 demo 的重點是展示：AI 可以失敗，但 harness 要能抓到、縮小範圍、重跑，不能讓假成功混過去。

## 5. 如何啟動 dashboard

### 產生一筆 mock run

在專案根目錄執行：

```bash
python3 scripts/run_ai_company_task_harness.py docs/ai_specs/general-task-mock-replan.json --mode mock
```

### 啟動 dashboard

Windows 可以用：

```powershell
.\agent_os_mvp\start-dashboard.ps1
```

預設網址：

```text
Frontend: http://127.0.0.1:5174/
Backend:  http://127.0.0.1:8010/
```

如果你的電腦已經有其他 dashboard 佔用 port，可以改用其他 port，例如：

```text
Frontend: http://127.0.0.1:5175/
Backend:  http://127.0.0.1:8011/
```

## 6. 最簡單的閱讀順序

第一次看 dashboard，照這個順序：

1. 看 `Run Overview`
2. 看 `What Needs Attention`
3. 看 `Pipeline Timeline`
4. 如果有問題，看 `Agents`
5. 如果想知道為什麼被擋，看 `Guards`
6. 如果想看證據，看 `Artifacts`
7. 需要除錯才看 `Debug`

