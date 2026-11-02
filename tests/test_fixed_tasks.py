import unittest
from datetime import date
from fixed_tasks import monthly_occurrences


class FixedTasksTests(unittest.TestCase):
    def dates(self, anchor, month):
        record={'통합ID':'fixed','마감일':anchor,'시작일':anchor}
        return [r['마감일'] for r in monthly_occurrences([record],date.fromisoformat(month))]

    def test_weekend_and_original_anchor(self):
        self.assertIn('2026-08-17',self.dates('2026-07-15','2026-08-01'))
        self.assertIn('2026-09-15',self.dates('2026-07-15','2026-09-01'))

    def test_month_end_spills_into_next_month(self):
        self.assertIn('2026-11-02',self.dates('2026-10-31','2026-11-01'))
        self.assertIn('2027-03-01',self.dates('2026-01-31','2027-02-01'))

    def test_weekday_and_start_boundary(self):
        self.assertIn('2026-11-12',self.dates('2026-11-12','2026-11-01'))
        self.assertEqual([],self.dates('2026-12-12','2026-10-01'))

    def test_leap_year_and_invalid_date(self):
        self.assertIn('2028-02-29',self.dates('2026-01-31','2028-02-01'))
        self.assertEqual([],monthly_occurrences([{'마감일':'bad'}],date(2026,11,1)))
