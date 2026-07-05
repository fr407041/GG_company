# KPI Checklist

Use this checklist before marking a run as complete.

- Meeting converges within bounded rounds.
- Every dispatched task has owner, scope, and fallback.
- Prompt scope is small enough to reduce overflow pressure.
- Status file or event log reflects the latest state.
- Timeout, router error, and overflow are handled explicitly.
- False success is blocked by review or artifact checks.
- Post-verify scoring is recorded in a measurable way.
