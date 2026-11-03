import unittest

from incalc.app import (AverageCostForm, AverageMaturityForm, BondForm, InstallmentForm,
                        TermDepositForm, TOOLS)


class FormTests(unittest.TestCase):
    def test_every_tool_builds_a_form_that_needs_input(self):
        for tool in TOOLS:
            result, missing = tool.form().evaluate()
            self.assertIsNone(result, tool.flag)
            self.assertTrue(missing, tool.flag)

    def test_typing_a_monthly_return_clears_the_annual_one(self):
        form = InstallmentForm()
        form.state.update(price="1200", months="12", annual="40")
        form.state["monthly"] = "3"
        form.on_edit("monthly", "3")
        self.assertEqual(form.state["annual"], "")
        result, missing = form.evaluate()
        self.assertIsNone(missing)
        self.assertEqual(len(result.rows), 12)

    def test_installment_toggle_switches_first_payment(self):
        form = InstallmentForm()
        form.state.update(price="1200", months="12", monthly="3")
        form.on_toggle()
        self.assertEqual(form.evaluate()[0].rows[0].label, "now")

    def test_bond_frequency_toggle_resyncs_coupon_rate(self):
        form = BondForm()
        form.state["annual_rate"] = "20"
        form.on_edit("annual_rate", "0")
        self.assertEqual(form.state["coupon_rate"], "20")
        form.on_toggle()
        self.assertEqual(form.frequency, "semiannual")
        self.assertEqual(form.state["coupon_rate"], "10")

    def test_bond_days_fill_maturity(self):
        form = BondForm()
        form.state.update(nominal="1000", dirty_price="85.4", days="365", annual_rate="0")
        form.on_edit("days", "5")
        result, missing = form.evaluate()
        self.assertIsNone(missing)
        self.assertAlmostEqual(result.total_cost, 854)

    def test_average_form_opens_a_new_row_when_the_last_is_complete(self):
        form = AverageCostForm()
        form.state["quantity:0"] = "10"
        form.on_edit("quantity:0", "0")
        self.assertEqual(form.count, 1)
        form.state["price:0"] = "5"
        form.on_edit("price:0", "5")
        self.assertEqual(form.count, 2)
        self.assertEqual(len(form.visible_fields()), 4)
        form.state.update({"quantity:1": "30", "price:1": "9"})
        self.assertAlmostEqual(form.evaluate()[0].average_cost, 8)

    def test_average_maturity_reports_invalid_entries(self):
        form = AverageMaturityForm()
        form.state.update({"amount:0": "0", "days:0": "10"})
        result, missing = form.evaluate()
        self.assertIsNone(result)
        self.assertIn("positive", missing)

    def test_term_deposit_comparison_table_covers_every_term(self):
        form = TermDepositForm()
        form.state.update(principal="100000", annual_rate="40", days="32")
        result, _ = form.evaluate()
        self.assertEqual(len(form.table(result).rows), 6)


if __name__ == "__main__":
    unittest.main()
