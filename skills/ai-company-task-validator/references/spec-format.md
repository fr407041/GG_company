# Spec Format

Use a JSON object with:

- `id`: stable case id.
- `goal`: user-facing task goal.
- `strategy`: bounded planning summary.
- `scope_subdir`: repo-relative working directory.
- `jobs`: list of task objects.
- `expectations`: KPI thresholds used by the harness.

Each job may include:

- `id`
- `title`
- `instruction`
- `files`
- `success_check`
- `require_change`
- `test_command`
- `mock_status`

Recommended generic cases:

- one evidence-oriented job
- one synthesis-oriented job
- optional forced `mock_status: NEEDS_REPLAN` for bounded recovery tests
