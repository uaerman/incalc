import unittest

from incalc.finance.real_return import calculate


class RealReturnTests(unittest.TestCase):
    def test_fisher_equation_after_tax(self):
        result = calculate(nominal_return=20, tax=10, inflation=10)
        self.assertAlmostEqual(result.net_nominal_return, 18)
        self.assertAlmostEqual(result.real_return, ((1.18 / 1.10) - 1) * 100, places=8)

    def test_inflation_can_outpace_a_positive_nominal_return(self):
        result = calculate(nominal_return=10, inflation=20)
        self.assertLess(result.real_return, 0)


if __name__ == "__main__":
    unittest.main()
