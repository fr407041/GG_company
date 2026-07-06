# Invoice Normalizer

This tiny repo normalizes invoice amounts into signed integer cents.

Expected rules:

- Plain decimals like `12.34` should become `1234`.
- Currency symbols and commas should be ignored.
- Parentheses mean the amount is negative, so `($45.67)` should become `-4567`.
- Inputs with no numeric content should raise `ValueError`.

The current implementation mishandles parenthesized negative amounts and some whitespace-heavy inputs.
