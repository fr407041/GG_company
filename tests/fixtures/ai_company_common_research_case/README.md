# Common Research Example

This fixture is a generic bounded research case for the ai-company orchestration flow.

Replace these files to adapt it:
- `research_brief.md`
- `evidence_summary.txt`
- `artifact_requirements.json`

The prep script will build:
- `summary_context.txt`
- `summary_compact_context.txt`

The child worker only reads `summary_compact_context.txt`.
