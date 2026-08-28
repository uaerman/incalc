import unittest

from incalc.finance.weighted_average import average_cost, average_maturity


class WeightedAverageTests(unittest.TestCase):
    def test_average_cost_is_weighted_by_quantity(self):
        result = average_cost([(10, 100), (30, 200)])
        self.assertEqual(result.total_cost, 7_000)
        self.assertEqual(result.average_cost, 175)

    def test_average_maturity_is_weighted_by_amount(self):
        result = average_maturity([(1_000, 30), (3_000, 90)])
        self.assertEqual(result.average_days, 75)


if __name__ == "__main__":
    unittest.main()
