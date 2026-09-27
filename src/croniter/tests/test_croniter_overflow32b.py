#!/usr/bin/env python
"""
Regression tests for the 32-bit `time_t` overflow.

On 32-bit platforms ``datetime.datetime.fromtimestamp()`` relies on the C
``time_t`` type and raises ``OverflowError`` for timestamps outside the
[1901-12-13, 2038-01-19] range
(see https://github.com/python/cpython/issues/101069). croniter must not
depend on the platform ``time_t`` width, so these tests simulate such a
platform by making ``fromtimestamp`` raise ``OverflowError`` outside the
32-bit range, and check that croniter keeps working with out-of-range dates.
"""
# -*- coding: utf-8 -*-

import unittest
from datetime import datetime, timezone

from croniter import cron_m, croniter, croniter_range
from croniter.tests import base

# 32-bit signed time_t bounds, as UNIX timestamps.
INT32_MIN = -(2**31)
INT32_MAX = 2**31 - 1


class _OverflowingDateTime(datetime):
    """
    ``datetime.datetime`` as it behaves on a 32-bit platform: ``fromtimestamp``
    raises ``OverflowError`` outside the 32-bit ``time_t`` range.
    """

    @classmethod
    def fromtimestamp(cls, timestamp, tz=None):
        if not INT32_MIN <= timestamp <= INT32_MAX:
            raise OverflowError("timestamp out of range for platform time_t")
        return datetime.fromtimestamp(timestamp, tz)


class _DatetimeModuleShim:
    """
    Stand-in for the ``datetime`` module of a 32-bit platform: identical to
    the real module, except that ``datetime`` is `_OverflowingDateTime`.
    """

    def __init__(self, real_module):
        self._real_module = real_module
        self.datetime = _OverflowingDateTime

    def __getattr__(self, name):
        return getattr(self._real_module, name)


def ts(d):
    """Naive UTC datetime -> UNIX timestamp, without fromtimestamp()."""
    return (d - datetime(1970, 1, 1)).total_seconds()


class CroniterOverflow32bTest(base.TestCase):
    def setUp(self):
        self._real_datetime_module = cron_m.datetime
        cron_m.datetime = _DatetimeModuleShim(self._real_datetime_module)
        # isinstance()/issubclass() checks inside croniter compare against the
        # shimmed class, so test datetimes must be built from it too.
        self.datetime = cron_m.datetime.datetime
        # EPOCH was built at import time from the real class; rebuild it from
        # the shimmed one so every datetime croniter produces is an instance
        # of the shimmed class, exactly like on a real 32-bit platform.
        self._real_epoch = cron_m.EPOCH
        cron_m.EPOCH = self.datetime(1970, 1, 1, tzinfo=timezone.utc)

    def tearDown(self):
        cron_m.datetime = self._real_datetime_module
        cron_m.EPOCH = self._real_epoch

    def test_get_next_beyond_2038(self):
        itr = croniter("* * * * *", self.datetime(2040, 1, 1, 0, 0))
        self.assertEqual(itr.get_next(), ts(datetime(2040, 1, 1, 0, 1)))
        self.assertEqual(itr.get_next(self.datetime), datetime(2040, 1, 1, 0, 2))

    def test_get_prev_before_1901(self):
        itr = croniter("* * * * *", self.datetime(1900, 1, 1, 0, 0))
        self.assertEqual(itr.get_prev(), ts(datetime(1899, 12, 31, 23, 59)))
        self.assertEqual(itr.get_prev(self.datetime), datetime(1899, 12, 31, 23, 58))

    def test_timestamp_to_datetime_beyond_2038(self):
        itr = croniter("* * * * *", self.datetime(2040, 1, 1))
        self.assertEqual(
            itr.timestamp_to_datetime(ts(datetime(2045, 6, 7, 8, 9, 10))),
            datetime(2045, 6, 7, 8, 9, 10),
        )

    def test_timestamp_to_datetime_beyond_2038_aware(self):
        itr = croniter("* * * * *", self.datetime(2040, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(
            itr.timestamp_to_datetime(ts(datetime(2045, 6, 7, 8, 9, 10))),
            datetime(2045, 6, 7, 8, 9, 10, tzinfo=timezone.utc),
        )

    def test_croniter_range_beyond_2038(self):
        start = ts(datetime(2040, 1, 1))
        stop = ts(datetime(2040, 1, 4))
        self.assertEqual(
            list(croniter_range(start, stop, "0 0 * * *")),
            [ts(datetime(2040, 1, day)) for day in (1, 2, 3, 4)],
        )

    def test_expand_from_start_time_beyond_2038(self):
        itr = croniter(
            "*/15 * * * *", self.datetime(2040, 1, 1, 0, 7), expand_from_start_time=True
        )
        self.assertEqual(itr.get_next(self.datetime), datetime(2040, 1, 1, 0, 22))

    def test_match_beyond_2038(self):
        self.assertTrue(croniter.match("* * * * *", self.datetime(2040, 1, 1, 0, 0)))
        self.assertFalse(croniter.match("7 * * * *", self.datetime(2040, 1, 1, 0, 0)))


if __name__ == "__main__":
    unittest.main()
