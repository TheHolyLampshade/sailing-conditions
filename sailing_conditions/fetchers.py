import requests, re, sys
from typing import Optional, List
from .config import NWS_UA, TGFTP_ROOT, NDBC_REALTIME

def http_get(url: str, timeout=20):
    return requests.get(url, timeout=timeout, headers={"User-Agent": NWS_UA}, allow_redirects=True)

def fetch_tgftp_text(rel_path: str) -> Optional[str]:
    """Resilient TGFTP fetch: try with and without trailing slash."""
    base = f"{TGFTP_ROOT}/{rel_path.lstrip('/')}"
    try_order = [base, base.rstrip('/'), base.rstrip('/') + '/']
    seen = set()
    for url in try_order:
        if url in seen: continue
        seen.add(url)
        try:
            r = http_get(url)
            if r.status_code == 200 and r.text.strip():
                return r.text
        except Exception as e:
            short = url.replace(TGFTP_ROOT + '/', '')
            print(f"[warn] TGFTP fetch failed {short}: {e}", file=sys.stderr)
    return None

def fetch_city_marine_text(zones: List[str]) -> Optional[str]:
    buf = []
    for z in zones:
        t = fetch_tgftp_text(z)
        if t:
            buf.append(f"\n\n===== {z.upper()} =====\n{t.strip()}\n")
    return "\n".join(buf).strip() if buf else None

def fetch_grid_periods(lat: float, lon: float) -> Optional[List[dict]]:
    try:
        p = http_get(f"https://api.weather.gov/points/{lat},{lon}")
        p.raise_for_status()
        fc_url = p.json()["properties"]["forecast"]
        f = http_get(fc_url)
        f.raise_for_status()
        return f.json()["properties"]["periods"]
    except Exception as e:
        print(f"[warn] Gridpoint fetch failed: {e}", file=sys.stderr)
        return None

def grid_pick_day(periods, label: str):
    """
    Pick the most appropriate NWS grid 'forecast' period for a given label.

    Strategy:
    - Resolve the target calendar date from the label ("TODAY", "TOMORROW", weekday names).
    - Prefer periods whose startTime.date() == target_date.
    - For 'today-ish' labels, prefer daytime-ish names ("Today", "This Afternoon", "This Morning", "This Evening").
    - Otherwise, return the first period matching the date.
    """
    import datetime as dt

    if not periods:
        return None

    label_up = (label or "").strip().upper()
    now = dt.datetime.now().astimezone()
    today = now.date()

    # Resolve target date from label
    if label_up in ("REST OF TODAY", "TODAY"):
        target_date = today
        todayish = True
    elif label_up == "TOMORROW":
        target_date = today + dt.timedelta(days=1)
        todayish = False
    else:
        # Weekday name like "SATURDAY" / "SUNDAY" etc.
        weekdays = ["MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY","SATURDAY","SUNDAY"]
        if label_up in weekdays:
            target_wd = weekdays.index(label_up)
            # find next date with that weekday (including today if it matches)
            delta = (target_wd - today.weekday()) % 7
            target_date = today + dt.timedelta(days=delta)
            todayish = False
        else:
            # Fallback: assume today
            target_date = today
            todayish = True

    # Parse the period dates and filter to the target date
    def _pdate(p):
        # ISO8601 like "2025-08-15T18:00:00-05:00"
        try:
            return dt.datetime.fromisoformat(p.get("startTime")).astimezone().date()
        except Exception:
            return None

    same_day = [p for p in periods if _pdate(p) == target_date]
    if not same_day:
        return None

    # For today-ish, prefer explicit dayparts commonly used by NWS
    if todayish:
        name_pref_order = ["today", "this afternoon", "this morning", "this evening"]
        # try to find first matching preferred name
        for cand in name_pref_order:
            for p in same_day:
                nm = (p.get("name") or "").strip().lower()
                if cand == "today" and nm == "today":
                    return p
                if cand != "today" and cand in nm:
                    return p
        # otherwise just take the first for the date
        return same_day[0]

    # Non-today cases: weekend/weekday labels — return the first for that date
    return same_day[0]

def fetch_ndbc_latest(station: str) -> Optional[dict]:
    try:
        r = requests.get(NDBC_REALTIME.format(station=station), timeout=15)
        r.raise_for_status()
        lines = [ln.strip() for ln in r.text.splitlines() if ln.strip() and not ln.startswith("#")]
        if len(lines) < 2: return None
        header = lines[0].split(); data = lines[1].split()
        idx = {k:i for i,k in enumerate(header)}
        def to_int(s): 
            try: return int(s)
            except: return None
        def to_float(s):
            try: return float(s)
            except: return None
        for k in ["YY","MM","DD","hh","mm","WDIR","WSPD"]:
            if k not in idx: return None
        YY = 2000 + to_int(data[idx["YY"]]); MM = to_int(data[idx["MM"]]); DD = to_int(data[idx["DD"]])
        hh = to_int(data[idx["hh"]]); mm = to_int(data[idx["mm"]])
        if None in (YY,MM,DD,hh,mm): return None
        wdir = to_int(data[idx["WDIR"]]); wspd_ms = to_float(data[idx["WSPD"]]); wgst_ms = to_float(data[idx.get("GST",-1)]) if "GST" in idx else None
        ms_to_kt = 1.943844
        wspd_kt = round(wspd_ms*ms_to_kt,1) if wspd_ms is not None else None
        wgst_kt = round(wgst_ms*ms_to_kt,1) if wgst_ms is not None else None
        return {"wdir_deg": wdir, "wspd_kt": wspd_kt, "wgst_kt": wgst_kt}
    except Exception as e:
        print(f"[warn] NDBC fetch failed: {e}", file=sys.stderr)
        return None