from __future__ import annotations

import unittest

from invoice_tools.normalize import normalize_amount_to_cents


class NormalizeAmountTests(unittest.TestCase):
    def test_plain_decimal(self) -> None:
        self.assertEqual(normalize_amount_to_cents("12.34"), 1234)

    def test_currency_and_commas(self) -> None:
        self.assertEqual(normalize_amount_to_cents("$1,234.56"), 123456)

    def test_parenthesized_negative_amount(self) -> None:
        self.assertEqual(normalize_amount_to_cents("($45.67)"), -4567)

    def test_whitespace_heavy_negative_amount(self) -> None:
        self.assertEqual(normalize_amount_to_cents(" ( $8.90 ) "), -890)

    def test_invalid_text_raises(self) -> None:
        with self.assertRaises(ValueError):
            normalize_amount_to_cents("invoice pending")


if __name__ == "__main__":
    unittest.main()
