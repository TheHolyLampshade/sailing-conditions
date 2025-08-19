NWS_UA = "SailingQuickHits/6.0 (contact: you@example.com)"
TGFTP_ROOT = "https://tgftp.nws.noaa.gov/data/forecasts"

# Chicago nearshore LMZ set + CHII2 obs
CHICAGO_NEARSHORE = [
    "marine/near_shore/lm/lmz740.txt",
    "marine/near_shore/lm/lmz741.txt",
    "marine/near_shore/lm/lmz742.txt",
    "marine/near_shore/lm/lmz743.txt",
    "marine/near_shore/lm/lmz744.txt",
    "marine/near_shore/lm/lmz745.txt",
]
NDBC_STATION = "CHII2"  # Harrison-Dever Crib
NDBC_REALTIME = "https://www.ndbc.noaa.gov/data/realtime2/{station}.txt"

DEFAULT_KEYS = ["chicago", "philly", "kc", "slc", "nyc"]