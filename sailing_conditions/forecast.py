from typing import Dict, Optional, Tuple
from .fetchers import (
    fetch_city_marine_text,
    fetch_grid_periods,
    grid_pick_day,
    fetch_tgftp_text,
    fetch_ndbc_latest,
)
from .parsers import (
    parse_wind,
    parse_waves,
    parse_sky,
    compute_rating,
    extract_day_blurb,
    extract_today_blurb,
)
from .emoji import pick_weather_emoji, compose_prefix_emoji
from .config import CHICAGO_NEARSHORE, NDBC_STATION
from .cities import CITIES


def _wind_from_grid(p):
    """
    Robustly parse NWS grid 'windSpeed' strings:
      - "10 to 15 mph"
      - "15 mph"
      - "around 5 mph"
      - "north wind 5 to 10 mph"
      - "light and variable" / "calm"
    Returns (lo, hi) in knots or None.
    """
    import re

    wind_text = (p.get("windSpeed") or "").strip().lower()

    m_rng = re.search(r"(\d{1,2})\D+(\d{1,2})\s*mph", wind_text)
    if m_rng:
        lo, hi = int(m_rng.group(1)), int(m_rng.group(2))
        return (round(lo * 0.868976), round(hi * 0.868976))

    m_one = re.search(r"(\d{1,2})\s*mph", wind_text)
    if m_one:
        v = int(m_one.group(1))
        v_kt = round(v * 0.868976)
        return (max(0, v_kt - 1), v_kt + 1)

    m_around = re.search(r"around\s+(\d{1,2})\s*mph", wind_text)
    if m_around:
        v = int(m_around.group(1))
        v_kt = round(v * 0.868976)
        return (max(0, v_kt - 1), v_kt + 1)

    m_dir_rng = re.search(
        r"(north|northeast|east|southeast|south|southwest|west|northwest)\s+wind\s+(\d{1,2})\D+(\d{1,2})\s*mph",
        wind_text,
    )
    if m_dir_rng:
        lo, hi = int(m_dir_rng.group(2)), int(m_dir_rng.group(3))
        return (round(lo * 0.868976), round(hi * 0.868976))

    if "light" in wind_text or "variable" in wind_text or "calm" in wind_text:
        return (0, 5)

    return None


def chicago_forecast(label: str) -> Dict:
    # Build marine text from LMZ files
    full = []
    for rel in CHICAGO_NEARSHORE:
        t = fetch_tgftp_text(rel)
        if t:
            full.append(t)
    marine_text = "\n\n".join(full)

    # Try exact-day extraction; if missing, fall back to the first "today-ish" block
    sec = extract_day_blurb(marine_text, label) if marine_text else None
    if not sec and marine_text:
        sec = extract_today_blurb(marine_text)

    wdir = None
    wrng = None
    waves = None
    sky = None
    hazards = sec or None

    if sec:
        wdir, wrng = parse_wind(sec)
        waves = parse_waves(sec)
        sky = parse_sky(sec)
    else:
        periods = fetch_grid_periods(CITIES["chicago"]["lat"], CITIES["chicago"]["lon"])
        if periods:
            p = grid_pick_day(periods, label.title())
            if p:
                wrng = _wind_from_grid(p)
                wdir = p.get("windDirection")
                sky = (p.get("shortForecast") or p.get("detailedForecast") or "").lower()
                waves = None
                hazards = sky

    # Blend CHII2 obs
    obs = fetch_ndbc_latest(NDBC_STATION)
    if obs and obs.get("wspd_kt") is not None:
        comp = _deg_to_compass(obs.get("wdir_deg"))
        if wrng:
            lo, hi = wrng
            mid = int(round(obs["wspd_kt"]))
            if abs(((lo + hi) // 2) - mid) >= 4:
                wrng = (min(lo, mid), max(hi, mid))
        else:
            mid = int(round(obs["wspd_kt"]))
            wrng = (max(0, mid - 1), mid + 1)
        if not wdir and comp:
            wdir = comp

    rating = compute_rating(wrng, waves, sky)
    wind_line = _format_wind(wdir, wrng)
    waves_line = _format_waves(waves)
    sky_line = sky.title() if sky else "—"
    weather_emoji = pick_weather_emoji(True, rating, sky, waves, wrng, hazards, None, False)
    prefix = compose_prefix_emoji(True, rating, weather_emoji)
    quick = f"{label.title()}: {rating}/10. Wind {wind_line}, waves {waves_line}, {sky_line}."
    return _pack("Chicago", label, rating, wind_line, waves_line, sky_line, True, quick, prefix)


def marine_city_forecast(city_key: str, label: str) -> Dict:
    meta = CITIES[city_key]
    marine_text = fetch_city_marine_text(meta.get("marine_zones") or [])
    wdir = wrng = waves = sky = None
    hazards = marine_text or None

    if marine_text:
        sec = extract_day_blurb(marine_text, label)
        if not sec:
            # cover more headings commonly used in ANZ/AMZ/PZZ products
            if label.upper() in (
                "REST OF TODAY",
                "TODAY",
                "THIS AFTERNOON",
                "LATE THIS AFTERNOON",
                "THIS MORNING",
                "DAYTIME",
            ):
                sec = extract_today_blurb(marine_text)
        if sec:
            wdir, wrng = parse_wind(sec)
            waves = parse_waves(sec)
            sky = parse_sky(sec)
            hazards = sec

    temp_f = None
    if wrng is None and waves is None and sky is None:
        periods = fetch_grid_periods(meta["lat"], meta["lon"])
        if periods:
            p = grid_pick_day(periods, label.title())
            if p:
                wrng = _wind_from_grid(p)
                wdir = p.get("windDirection")
                sky = (p.get("shortForecast") or p.get("detailedForecast") or "").lower()
                temp_f = p.get("temperature")
                waves = None
                hazards = sky

    rating = compute_rating(wrng, waves, sky)
    wind_line = _format_wind(wdir, wrng)
    waves_line = _format_waves(waves)
    sky_line = sky.title() if sky else "—"
    weather_emoji = pick_weather_emoji(True, rating, sky, waves, wrng, hazards, temp_f, False)
    prefix = compose_prefix_emoji(True, rating, weather_emoji)
    quick = f"{label.title()}: {rating}/10. Wind {wind_line}, waves {waves_line}, {sky_line}."
    return _pack(meta["label"], label, rating, wind_line, waves_line, sky_line, True, quick, prefix)


def grid_city_forecast(city_key: str, label: str) -> Dict:
    meta = CITIES[city_key]
    periods = fetch_grid_periods(meta["lat"], meta["lon"])
    wdir = wrng = waves = sky = None
    temp_f = None
    if periods:
        p = grid_pick_day(periods, label.title())
        if p:
            wrng = _wind_from_grid(p)
            wdir = p.get("windDirection")
            sky = (p.get("shortForecast") or p.get("detailedForecast") or "").lower()
            temp_f = p.get("temperature")

    rating = compute_rating(wrng, waves, sky)
    wind_line = _format_wind(wdir, wrng)
    waves_line = "—"
    sky_line = sky.title() if sky else "—"
    weather_emoji = pick_weather_emoji(
        meta["sailing"], rating, sky, None, wrng, sky, temp_f, not meta["sailing"]
    )
    prefix = compose_prefix_emoji(meta["sailing"], rating, weather_emoji)
    quick = f"{label.title()}: {rating}/10. Wind {wind_line}, waves {waves_line}, {sky_line}."
    return _pack(meta["label"], label, rating, wind_line, waves_line, sky_line, meta["sailing"], quick, prefix)


# helpers used by cli.py to decide which "today" label to fetch
def _pick_present_day_label(marine_text: str) -> str:
    """
    Pick the best daytime label that actually exists in the marine text.
    Priority: REST OF TODAY > TODAY > THIS AFTERNOON > LATE THIS AFTERNOON > THIS MORNING > DAYTIME
    """
    from .parsers import extract_day_blurb

    if not marine_text:
        return "TODAY"
    candidates = [
        "REST OF TODAY",
        "TODAY",
        "THIS AFTERNOON",
        "LATE THIS AFTERNOON",
        "THIS MORNING",
        "DAYTIME",
    ]
    for cand in candidates:
        if extract_day_blurb(marine_text, cand):
            return cand
    return "TODAY"


def _deg_to_compass(deg):
    if deg is None:
        return None
    dirs = [
        "N",
        "NNE",
        "NE",
        "ENE",
        "E",
        "ESE",
        "SE",
        "SSE",
        "S",
        "SSW",
        "SW",
        "WSW",
        "W",
        "WNW",
        "NW",
        "NNW",
    ]
    i = int((deg / 22.5) + 0.5) % 16
    return dirs[i]


def _format_wind(wdir, wrng):
    if wrng and wdir:
        return f"{wdir} {wrng[0]}–{wrng[1]} kt"
    if wrng:
        return f"{wrng[0]}–{wrng[1]} kt"
    if wdir:
        return wdir
    return "—"


def _format_waves(waves):
    if not waves:
        return "—"
    lo, hi = waves
    return f"{lo}–{hi} ft" if abs(hi - lo) > 0.1 else f"{lo} ft"


def _pack(city, label, rating, wind, waves, sky, sailing, quick, prefix):
    return {
        "city": city,
        "label": label.title(),
        "rating": rating,
        "wind_line": wind,
        "waves_line": waves,
        "sky_line": sky,
        "sailing": sailing,
        "quick": quick,
        "prefix": prefix,
    }