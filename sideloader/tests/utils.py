"""
Assorted utilities that we really shouldn't have to write ourselves.
"""

from datetime import datetime, timedelta, tzinfo


class UTC(tzinfo):
    """
    Why does the standard library not already have a UTC tzinfo?
    """
    def utcoffset(self, dt):
        return timedelta(0)

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return timedelta(0)

utc = UTC()


def datetime_utc(*args):
    return datetime(*args, tzinfo=utc)


def now_utc():
    return datetime.now(utc)


def dictmerge(dct, **kw):
    """
    Because there's no non-mutating equivalent of dict.update().
    """
    dct = dct.copy()
    dct.update(kw)
    return dct
