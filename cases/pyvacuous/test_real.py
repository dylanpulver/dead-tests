import unittest


class TestReal(unittest.TestCase):
    def test_depreciation_schedule(self):
        expected_values = [["2022-06-30", 20000.0, False]]
        for i, schedule in enumerate(get_schedule()):
            self.assertEqual(expected_values[i][0], schedule.schedule_date)
            self.assertEqual(expected_values[i][1], schedule.amount)
            # Reported: nothing else compares this expression to anything.
            self.assertEqual(schedule.journal_entry, schedule.journal_entry)

    def test_blanket_order_rate(self):
        po = make_order()
        bo = get_blanket()
        # Reported: subscript plus attribute, no call, no sibling comparison.
        self.assertEqual(po.items[0].rate, po.items[0].rate)
        self.assertEqual(po.items[0].qty, bo.items[0].ordered_qty)


def get_schedule():
    return []


def make_order():
    return None


def get_blanket():
    return None
