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

    def test_no_tool_flag_opens_the_selector(self):
        self.assertIsNone(parse_args([]).tool)

    def test_tool_flags_select_their_tools(self):
        self.assertEqual(parse_args(["--yield"]).tool, "yield")
        self.assertEqual(parse_args(["--tax"]).tool, "tax")
        self.assertEqual(parse_args(["--bond-yield"]).tool, "bond-yield")
        self.assertEqual(parse_args(["--real-return"]).tool, "real-return")
        self.assertEqual(parse_args(["--term-deposit"]).tool, "term-deposit")

    def test_ctrl_c_exits_without_a_traceback(self):
        with patch("incalc.app.curses.wrapper", side_effect=KeyboardInterrupt):
            self.assertEqual(main(["--yield"]), 130)

    def test_tool_search_filters_by_name_description_and_flag(self):
        self.assertEqual([tool.flag for tool in search_tools("bond")], ["bond-yield"])
        self.assertEqual([tool.flag for tool in search_tools("inflation")], ["real-return"])


if __name__ == "__main__":
    unittest.main()
