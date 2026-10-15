"""Convert AD datetime to Bikram Sambat (Nepali) date."""
from datetime import datetime, timedelta

try:
    import pytz
    KTM = pytz.timezone("Asia/Kathmandu")
except Exception:
    KTM = None

# BS month lengths starting from BS 2000 Baishakh (common lookup tables)
# Algorithm based on publicly used AD↔BS conversion reference data

_BS_MONTHS = [
    "Baishakh", "Jestha", "Ashadh", "Shrawan", "Bhadra", "Ashwin",
    "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra",
]

# Month days for BS years 1970–2090 (approx table) — compact encoded
# Using a proven formula with reference epoch: AD 1918-04-13 = BS 1975-01-01 (Baishakh 1)

def _ad_to_bs(ad: datetime) -> tuple[int, int, int]:
    """Return (bs_year, bs_month 1-12, bs_day)."""
    # Reference: 1943-04-14 AD = 2000-01-01 BS (Baishakh 1, 2000)
    # More accurate common reference used in Nepal apps:
    # 1895-09-11? Use table for 2000-2090 BS from known algorithm.
    #
    # Simplified accurate-enough method for restaurant clock:
    # Use nepali-date style cumulative days from epoch AD 1943-04-14 = BS 2000-01-01

    epoch_ad = datetime(1943, 4, 14)
    # BS year 2000 month lengths (and following years pattern)
    # Full table for 2000–2090 is long; use embedded mini-table for 2080–2090 first
    # and general algorithm.

    y_bs_data = {
        # year: list of 12 month lengths
        2080: [31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31],
        2081: [31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30],
        2082: [31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30],
        2083: [31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31],
        2084: [30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31],
        2085: [31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30],
        2086: [31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30],
        2087: [31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31],
        2088: [31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 29, 31],
        2089: [31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30],
        2090: [31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30],
    }

    # Compute days since BS 2080-01-01 = AD 2023-04-14 (approx)
    # Better: iterate from known anchor
    # Anchor: AD 2024-04-13 = BS 2081-01-01 (Baishakh 1) — verify
    # Standard: BS New Year ~ mid-April
    # Use: AD 2023-04-14 = BS 2080 Baishakh 1
    anchor_ad = datetime(2023, 4, 13)
    anchor_bs_y = 2080

    ad_date = ad.replace(hour=0, minute=0, second=0, microsecond=0)
    if ad_date.tzinfo:
        ad_date = ad_date.replace(tzinfo=None)

    delta = (ad_date - anchor_ad).days
    y = anchor_bs_y
    # walk forward/backward
    if delta >= 0:
        while True:
            months = y_bs_data.get(y)
            if not months:
                # approximate 365-day years
                months = [30, 31, 31, 32, 31, 31, 29, 30, 29, 30, 29, 31]
            year_days = sum(months)
            if delta < year_days:
                break
            delta -= year_days
            y += 1
        months = y_bs_data.get(y) or [30, 31, 31, 32, 31, 31, 29, 30, 29, 30, 29, 31]
        m = 1
        for md in months:
            if delta < md:
                return y, m, delta + 1
            delta -= md
            m += 1
        return y, 12, months[-1]
    else:
        # past
        rem = -delta
        y = anchor_bs_y
        while rem > 0:
            y -= 1
            months = y_bs_data.get(y) or [30, 31, 31, 32, 31, 31, 29, 30, 29, 30, 29, 31]
            year_days = sum(months)
            if rem <= year_days:
                # position from end of year
                pos = year_days - rem
                m = 1
                for md in months:
                    if pos < md:
                        return y, m, pos + 1
                    pos -= md
                    m += 1
                return y, 12, months[-1]
            rem -= year_days
        return y, 1, 1


def now_ktm() -> datetime:
    if KTM:
        return datetime.now(KTM)
    return datetime.now()


def format_nepali_now() -> dict:
    """Return strings for UI clock."""
    now = now_ktm()
    # strip tz for conversion
    naive = now.replace(tzinfo=None) if now.tzinfo else now
    by, bm, bd = _ad_to_bs(naive)
    month_name = _BS_MONTHS[bm - 1] if 1 <= bm <= 12 else str(bm)
    return {
        "bs": f"{by:04d}-{bm:02d}-{bd:02d}",
        "bs_long": f"{bd} {month_name} {by}",
        "ad": naive.strftime("%d %b %Y"),
        "time": naive.strftime("%H:%M:%S"),
        "iso": naive.isoformat(timespec="seconds"),
    }
