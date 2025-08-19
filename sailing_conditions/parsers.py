import re
from typing import Optional, Tuple

# Wind & direction
WIND_RE = re.compile(
    r"(\d{1,2})\s*(?:to|-|–|—)\s*(\d{1,2})\s*(?:kt|knots?)|(\d{1,2})\s*(?:kt|knots?)",
    re.IGNORECASE,
)
DIR_RE = re.compile(
    r"\b(NNE|ENE|ESE|SSE|SSW|WSW|WNW|NNW|N|NE|E|SE|S|SW|W|NW)\b", re.IGNORECASE
)

# Waves / seas — accept either word, with ranges or single values, plus "around X ft"
WAVE_RE = re.compile(
    r"(?:(?:waves?|seas?)\s*)?(?:around\s*)?(\d(?:\.\d)?)\s*(?:to|-|–|—)\s*(\d(?:\.\d)?)\s*(?:ft|feet)"
    r"|(?:(?:waves?|seas?)\s*)?(?:around\s*)?(\d(?:\.\d)?)\s*(?:ft|feet)",
    re.IGNORECASE,
)

WAVE_SPECIAL_PATTERNS = [
    # "1 ft or less", "less than 1 ft"
    re.compile(r"(?:1\s*ft\s*or\s*less|less\s*than\s*1\s*ft)", re.IGNORECASE),
    # "waves around X ft" / "seas around X ft"
    re.compile(r"(?:waves?|seas?)\s*around\s*(\d(?:\.\d)?)\s*(?:ft|feet)", re.IGNORECASE),
    # plain "around X ft"
    re.compile(r"\baround\s*(\d(?:\.\d)?)\s*(?:ft|feet)", re.IGNORECASE),
]

# Sky keywords (loose)
SKY_RE = re.compile(
    r"\b(sunny|clear|partly cloudy|mostly sunny|mostly clear|cloudy|showers|storms?|thunder|rain|overcast)\b",
    re.IGNORECASE,
)

# Sea-state word mappings (when numerics absent)
SEA_STATE_MAP = {
    "smooth": (0.1, 0.5),
    "light chop": (0.5, 1.5),
    "slight chop": (0.5, 1.5),
    "choppy": (1.5, 3.0),
    "moderate chop": (1.5, 3.0),
    "rough": (3.0, 5.0),
    "very rough": (4.0, 7.0),
    "heavy chop": (3.0, 5.0),
}
SEA_STATE_KEYS = tuple(sorted(SEA_STATE_MAP.keys(), key=len, reverse=True))


def parse_wind(text: str) -> Tuple[Optional[str], Optional[Tuple[int, int]]]:
    dm = DIR_RE.search(text or "")
    wdir = dm.group(0).upper() if dm else None
    sp = WIND_RE.search(text or "")
    if sp:
        if sp.group(1) and sp.group(2):
            lo, hi = int(sp.group(1)), int(sp.group(2))
        else:
            lo = hi = int(sp.group(3))
        return wdir, (lo, hi)
    return wdir, None


def parse_waves(text: str) -> Optional[Tuple[float, float]]:
    if not text:
        return None
    m = WAVE_RE.search(text)
    if m:
        if m.group(1) and m.group(2):
            return (float(m.group(1)), float(m.group(2)))
        v = float(m.group(3))
        return (v, v)
    for pat in WAVE_SPECIAL_PATTERNS:
        mm = pat.search(text)
        if mm and mm.groups():
            v = float(mm.group(1))
            return (max(0.1, v - 0.5), v + 0.5)
        if pat.search(text):
            return (0.5, 1.0)
    lower = (text or "").lower()
    for key in SEA_STATE_KEYS:
        if key in lower:
            return SEA_STATE_MAP[key]
    return None


def parse_sky(text: str) -> Optional[str]:
    m = SKY_RE.search(text or "")
    return m.group(0).lower() if m else None


def compute_rating(wind_kts, waves_ft, sky: Optional[str]) -> int:
    # If we truly have nothing, stay neutral
    if wind_kts is None and waves_ft is None and not sky:
        return 5

    score = 10
    # Waves penalty
    if waves_ft:
        hi = max(waves_ft)
        if hi > 5:
            score -= 6
        elif hi > 4:
            score -= 4
        elif hi > 3:
            score -= 2
    # Wind penalty/bonus
    if wind_kts:
        lo, hi = wind_kts
        if hi >= 28:
            score -= 6
        elif hi >= 23:
            score -= 4
        elif hi >= 18:
            score -= 2
        if lo < 5:
            score -= 2
        elif lo < 9:
            score -= 1
    # Sky bonus/penalty
    if sky:
        s = sky.lower()
        if "sunny" in s or "clear" in s:
            score += 1
        if "storm" in s or "thunder" in s:
            score -= 5
        if "showers" in s or "rain" in s:
            score -= 2

    return max(1, min(10, score))


def normalize_heading(h: str) -> str:
    import re as _re

    return _re.sub(r"\s+", " ", (h or "").strip().upper())


def extract_day_blurb(full_text: str, day_heading: str):
    import re as _re

    txt = (full_text or "").replace("\r", "")
    dh = normalize_heading(day_heading)
    pattern = rf"(?mis)^\s*\.?{_re.escape(dh)}(?:\s+NIGHT)?\.{{3,}}(.*?)(?=^\s*\.?[A-Z][A-Z /-]{{2,}}(?:\s+NIGHT)?\.{{3,}}|\Z)"
    m = _re.search(pattern, txt)
    return m.group(0).strip() if m else None


def extract_today_blurb(full_text: str) -> str:
    for c in [
        "REST OF TODAY",
        "TODAY",
        "THIS AFTERNOON",
        "LATE THIS AFTERNOON",
        "THIS MORNING",
        "DAYTIME",
    ]:
        sec = extract_day_blurb(full_text, c)
        if sec:
            return sec
    import re as _re

    m = _re.search(r"(?s)(?:\A|^\s*\n)(.*?)(?:\n\s*\n|\Z)", full_text or "")
    return (m.group(1).strip() if m else (full_text or ""))