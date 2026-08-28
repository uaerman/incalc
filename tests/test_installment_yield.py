import unittest

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


if __name__ == "__main__":
    unittest.main()
