from datetime import date
import unittest

from incalc.finance.bond_yield import calculate, coupon_dates
from incalc.app import sync_coupon_rates


class BondYieldTests(unittest.TestCase):
    def test_zero_coupon_bond_yield(self):
        result = calculate(
            nominal=100,
            dirty_price=95,
            maturity=date(2027, 1, 1),
            coupon_rate=0,
            frequency=1,
            settlement=date(2026, 1, 1),
        )
        self.assertEqual(result.total_cost, 95)
        self.assertEqual(result.principal_at_maturity, 100)
        self.assertAlmostEqual(result.annualized_return, 100 / 95 * 100 - 100, places=8)
        self.assertAlmostEqual(result.ytm, 100 / 95 * 100 - 100, places=8)

    def test_semiannual_coupon_dates_are_generated_back_from_maturity(self):
        dates = coupon_dates(date(2026, 1, 1), date(2027, 1, 1), 2)
        self.assertEqual(dates, [date(2026, 7, 1), date(2027, 1, 1)])

    def test_coupon_and_annual_rates_are_converted_by_frequency(self):
        state = {"coupon_rate": "2.5", "annual_rate": ""}
        sync_coupon_rates(state, "coupon_rate", "semiannual")
        self.assertEqual(state["annual_rate"], "5")
        state["annual_rate"] = "12"
        sync_coupon_rates(state, "annual_rate", "quarterly")
        self.assertEqual(state["coupon_rate"], "3")


if __name__ == "__main__":
    unittest.main()
