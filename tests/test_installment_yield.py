import unittest
from unittest.mock import patch

from incalc.app import main, parse_args, search_tools
from incalc.finance.installment_yield import calculate, schedule


class InstallmentYieldTests(unittest.TestCase):
    def test_schedule_puts_rounding_in_last_payment(self):
        self.assertEqual(schedule(100, 3), [33.33, 33.33, 33.34])

    def test_zero_return_means_no_discount(self):
        result = calculate(price=1200, months=12, monthly_percent=0)
        self.assertEqual(result.gross, 0)
        self.assertEqual(result.paid, 1200)

    def test_first_payment_now_has_no_first_period_return(self):
        result = calculate(price=1200, months=12, monthly_percent=1, pay_now=True)
        self.assertEqual(result.rows[0].label, "now")
        self.assertEqual(result.rows[0].earned, 0)

    def test_withholding_is_deducted_from_total_return(self):
        result = calculate(price=1_200, months=12, monthly_percent=1, tax_percent=10)
        self.assertGreater(result.tax, 0)
        self.assertLess(result.tax, result.gross * 0.10)
        self.assertAlmostEqual(result.net, result.gross - result.tax)

    def test_withholding_is_taken_from_each_redemption_profit_share(self):
        result = calculate(price=12_000, months=12, monthly_percent=1, tax_percent=10)
        self.assertAlmostEqual(result.tax, sum(row.withholding for row in result.rows) + result.final_withholding)
        self.assertGreater(result.rows[-1].withholding, result.rows[0].withholding)
        self.assertAlmostEqual(result.rows[-1].redeemed, result.rows[-1].payment + result.rows[-1].withholding)
        self.assertGreater(result.rows[-1].redeemed, result.rows[0].redeemed)
        self.assertGreater(result.hold_net, result.left)

    def test_final_fund_redemption_is_taxed(self):
        result = calculate(price=12_000, months=12, monthly_percent=1, tax_percent=10)
        self.assertGreater(result.final_withholding, 0)
        self.assertAlmostEqual(result.net, result.gross - result.tax)

    def test_no_tool_flag_opens_the_selector(self):
        self.assertIsNone(parse_args([]).tool)

    def test_tool_flags_select_their_tools(self):
        self.assertEqual(parse_args(["--yield"]).tool, "yield")
        self.assertEqual(parse_args(["--bond-yield"]).tool, "bond-yield")
        self.assertEqual(parse_args(["--real-return"]).tool, "real-return")
        self.assertEqual(parse_args(["--term-deposit"]).tool, "term-deposit")
        self.assertEqual(parse_args(["--profit-margin"]).tool, "profit-margin")
        self.assertEqual(parse_args(["--average-cost"]).tool, "average-cost")
        self.assertEqual(parse_args(["--average-maturity"]).tool, "average-maturity")

    def test_ctrl_c_exits_without_a_traceback(self):
        with patch("incalc.app.curses.wrapper", side_effect=KeyboardInterrupt):
            self.assertEqual(main(["--yield"]), 130)

    def test_tool_search_filters_by_name_description_and_flag(self):
        self.assertEqual([tool.flag for tool in search_tools("bond")], ["bond-yield"])
        self.assertEqual([tool.flag for tool in search_tools("inflation")], ["real-return"])


if __name__ == "__main__":
    unittest.main()
