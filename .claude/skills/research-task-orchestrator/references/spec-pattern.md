# Spec Pattern

A good task spec should include:

- objective
- scope limit
- output contract
- evidence expectations
- failure signals
- retry or replan policy

Recommended defaults:
- Keep child instructions narrow.
- Prefer prep-time evidence packaging over dumping raw context.
- Do not put large raw datasets directly into child prompts.
- Require a verify step before claiming success.
