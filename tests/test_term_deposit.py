import unittest

from incalc.finance.term_deposit import calculate, withholding_rate


class TermDepositTests(unittest.TestCase):
    def test_gross_net_and_maturity_balance(self):
        result = calculate(principal=100_000, annual_rate=40, days=365)
        self.assertEqual(result.gross_interest, 40_000)
        self.assertEqual(result.withholding_rate, 15)
        self.assertEqual(result.withholding, 6_000)
        self.assertEqual(result.net_interest, 34_000)
        self.assertEqual(result.maturity_balance, 134_000)

    def test_tl_withholding_brackets(self):
        self.assertEqual(withholding_rate(180), 17.5)
        self.assertEqual(withholding_rate(181), 15)
        self.assertEqual(withholding_rate(366), 10)


if __name__ == "__main__":
    unittest.main()
