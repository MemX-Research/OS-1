from enum import Enum
import time
from datetime import datetime, timedelta, date

import humanize


def get_timestamp():
    return int(datetime.timestamp(datetime.now()) * 1000)


def get_past_timestamp(days=0, day_start_hour=4, current_time=None):
    if current_time is None:
        current_time = get_timestamp()
    # everyday start from 4am
    now = datetime.fromtimestamp(current_time / 1000)
    if now.hour < day_start_hour:
        days += 1
    start_date = now.date() - timedelta(days=days)
    start_time = datetime(
        start_date.year, start_date.month, start_date.day, day_start_hour
    )
    return int(start_time.timestamp() * 1000)


def timestamp_to_str(timestamp, format="%Y-%m-%d %H:%M:%S"):
    return datetime.fromtimestamp(timestamp / 1000).strftime(format)


def get_timestamp_str():
    return timestamp_to_str(get_timestamp())


def str_to_timestamp(date_str, format="%Y-%m-%d %H:%M:%S"):
    return int(datetime.strptime(date_str, format).timestamp() * 1000)


def get_relative_time(current_time, including_today=True, now=None):
    if now is None:
        now = datetime.now()
    else:
        now = datetime.fromtimestamp(now / 1000)
    ago = datetime.fromtimestamp(current_time / 1000)
    if not including_today:
        return f"{humanize.naturaltime(now - timedelta(seconds=(now - ago).total_seconds()), when=now)}:"
    date_str = now.strftime("%Y-%m-%d %A")
    time_str = now.strftime("%H:%M:%S")
    period = get_period_of_day(now, return_str=True)
    return f"Today is {date_str}. It is {time_str} in {period}. Just {humanize.naturaltime(now - timedelta(seconds=(now - ago).total_seconds()), when=now)},"


class PeriodOfDay(Enum):
    MORNING = (5, 11)
    NOON = (11, 13)
    AFTERNOON = (13, 17)
    DUSK = (17, 19)
    EVENING = (19, 22)
    NIGHT = (22, 5)
    ALL = (5, 5)

    def range_with_offset(self, offset: int = -5):
        new_range = (self.value[0] + offset, self.value[1] + offset)
        if new_range[0] < 0:
            new_range = (24 + new_range[0], 24 + new_range[1])
        if new_range[1] == 0:
            new_range = (new_range[0], 24)
        return new_range

    @property
    def display_name(self):
        return self.name.lower()


def get_period_of_day(now, return_str=False):
    if isinstance(now, int):
        time_of_day = datetime.fromtimestamp(now / 1000).time()
    else:
        time_of_day = now.time()

    period = PeriodOfDay.NIGHT
    for p in PeriodOfDay:
        if time_of_day.hour >= p.value[0] and time_of_day.hour < p.value[1]:
            period = p
            break
    if return_str:
        return period.display_name
    return period
