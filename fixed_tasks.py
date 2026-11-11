"""Fixed-task projection; original dates remain the recurrence anchor."""
import calendar
from datetime import date, timedelta


def monthly_occurrences(records, month):
    weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(month.year, month.month)
    first, last = weeks[0][0], weeks[-1][-1]
    # Include the previous month because a weekend month-end can spill forward.
    cursor = first.replace(day=1)
    cursor = (cursor - timedelta(days=1)).replace(day=1)
    months = []
    while cursor <= last:
        months.append(cursor)
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    result = []
    for record in records:
        try:
            anchor = date.fromisoformat(record['마감일'])
            start = date.fromisoformat(record['시작일'] or record['마감일'])
        except (ValueError, TypeError, KeyError):
            continue
        if str(record.get('원본ID', '')).startswith('weekly:'):
            actual = max(first, anchor, start)
            actual += timedelta(days=(anchor.weekday()-actual.weekday()) % 7)
            while actual <= last:
                result.append(dict(record, 마감일=actual.isoformat(), 시작일=actual.isoformat()))
                actual += timedelta(days=7)
            continue
        for target in months:
            nominal = target.replace(day=min(anchor.day, calendar.monthrange(target.year, target.month)[1]))
            if nominal < anchor or nominal < start:
                continue
            actual = nominal + timedelta(days=7-nominal.weekday()) if nominal.weekday() >= 5 else nominal
            if first <= actual <= last:
                result.append(dict(record, 마감일=actual.isoformat(), 시작일=actual.isoformat()))
    return result
