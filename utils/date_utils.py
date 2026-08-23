# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from datetime import datetime


def is_leap_year(year: int) -> bool:
    return (year % 4 == 0) and (year % 100 != 0 or year % 400 == 0)


def convert_day(day: int, leap: bool = False) -> dict:
    months = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if leap:
        months[1] = 29
    month, remaining = 1, day
    for month_days in months:
        if remaining <= month_days:
            return {'month': month, 'day': remaining}
        remaining -= month_days
        month += 1
    return {'month': 12, 'day': 31}


def get_solar_date(date: datetime = None) -> tuple:
    if date is None:
        date = datetime.now()
    start = datetime(2023, 5, 1)
    month_start = datetime(date.year, date.month, 1)
    month_end = datetime(date.year + 1, 1, 1) if date.month == 12 else datetime(date.year, date.month + 1, 1)
    year = (month_start.year - start.year) * 12 + (month_start.month - start.month) + 2123
    year_len = (month_end - month_start).total_seconds() - 1
    point = (date - month_start).total_seconds()
    day_count = int((point / year_len) * (366 if is_leap_year(year) else 365))
    md = convert_day(day_count, is_leap_year(year))
    return (year, md['month'], md['day'])


def pretty_date(date: datetime = None) -> str:
    year, month, day = get_solar_date(date)
    return f"{year}/{month}/{day}"
