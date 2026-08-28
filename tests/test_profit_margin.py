import unittest

from incalc.finance.profit_margin import calculate


class ProfitMarginTests(unittest.TestCase):
    def test_margin_and_markup_are_distinct(self):
        result = calculate(unit_cost=100, unit_price=150, quantity=4)
        self.assertEqual(result.unit_profit, 50)
        self.assertEqual(result.total_profit, 200)
        self.assertAlmostEqual(result.profit_margin, 100 / 3)
        self.assertEqual(result.markup, 50)


if __name__ == "__main__":
    unittest.main()
