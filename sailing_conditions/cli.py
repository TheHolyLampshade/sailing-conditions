#!/usr/bin/env python3
import argparse, calendar
from datetime import date, timedelta
from typing import List
from .cities import CITIES
from .config import DEFAULT_KEYS
from .parsers import extract_day_blurb
from .fetchers import fetch_city_marine_text
from .forecast import chicago_forecast, marine_city_forecast, grid_city_forecast, _pick_present_day_label
from .formatters import format_slack_line_city, build_email_html
from .senders import send_email_html, post_slack

# Suggestions for non-sailing cities
OUTDOOR_SUGG = [
    "find a farmer’s market",
    "hit a park picnic",
    "catch a baseball game",
    "walk a new waterfront path",
    "try a rooftop spot",
    "rent a bike and explore",
]
INDOOR_SUGG = [
    "museum hop",
    "duck into a matinee",
    "bookstore + coffee crawl",
    "try an indoor food hall",
    "visit a gallery",
    "karaoke night",
]
NEUTRAL_SUGG = [
    "discover a neighborhood bakery",
    "brunch somewhere new",
    "cozy café + people-watch",
    "take a cooking class",
    "check a pop-up market",
]

RAINY_WORDS = {"rain", "showers", "thunder", "storm", "t-storm", "drizzle"}
SEVERE_WORDS = {"hazard", "warning", "gale", "storm", "hurricane", "hvy freezing spray"}


def _is_rainy(sky: str | None) -> bool:
    return bool(sky) and any(k in sky.lower() for k in RAINY_WORDS)


def pick_suggestion(city_label: str, sky: str | None) -> str:
    import os, random

    stable = os.environ.get("SUGGESTION_MODE", "").lower() == "stable"
    rng = random.Random(f"{city_label}-{date.today().isoformat()}") if stable else random.SystemRandom()

    if sky and any(k in sky.lower() for k in SEVERE_WORDS):
        return "Best bet: stay indoors and keep an eye on the radar."
    if _is_rainy(sky):
        return "Aw shoot — " + rng.choice(INDOOR_SUGG)
    if any(k in (sky or "").lower() for k in ["sunny", "clear"]):
        return rng.choice(OUTDOOR_SUGG)
    return rng.choice(NEUTRAL_SUGG)


def in_season(d: date) -> bool:
    last_may_day = max(day for day in range(31, 24, -1) if date(d.year, 5, day).weekday() == calendar.MONDAY)
    memorial_day = date(d.year, 5, last_may_day)
    first_sept_monday = next(day for day in range(1, 8) if date(d.year, 9, day).weekday() == calendar.MONDAY)
    labor_day = date(d.year, 9, first_sept_monday)
    return memorial_day <= d <= labor_day


def _resolve_city_selection(args, unknown: List[str]) -> List[str]:
    # Priority: --only > unknown --<key> flags & legacy flags > --all-cities > default
    if args.only:
        sel = [k.strip().lower() for k in args.only.split(",") if k.strip()]
        return [k for k in sel if k in CITIES] or DEFAULT_KEYS.copy()

    # unknown flags like --miami
    unk_keys = []
    for u in unknown:
        if u.startswith("--") and len(u) > 2 and "=" not in u:
            key = u[2:].lower().replace("-", "")
            if key in CITIES:
                unk_keys.append(key)

    legacy = []
    if args.chicago:
        legacy.append("chicago")
    if args.nyc:
        legacy.append("nyc")
    if args.philly:
        legacy.append("philly")
    if args.kc:
        legacy.append("kc")
    if args.slc:
        legacy.append("slc")

    candidates = list(dict.fromkeys(unk_keys + legacy))  # preserve order
    if args.all_cities:
        return list(CITIES.keys())
    if candidates:
        return candidates
    return DEFAULT_KEYS.copy()


def main():
    parser = argparse.ArgumentParser(description="Multi-city Sailing Quick Hits (refactored)")

    # Day (mutually exclusive)
    day = parser.add_mutually_exclusive_group()
    day.add_argument("--today", action="store_true", help="Use today's forecast (default)")
    day.add_argument("--tomorrow", action="store_true", help="Use tomorrow's forecast")
    day.add_argument("--weekend", action="store_true", help="Use Saturday & Sunday")

    # Delivery (independent)
    parser.add_argument("--email", action="store_true", help="Send to Email")
    parser.add_argument("--slack", action="store_true", help="Send to Slack")
    parser.add_argument("--all-delivery", action="store_true", help="Send to both Email and Slack")
    parser.add_argument("--all", action="store_true", help="Alias for both --all-cities and --all-delivery")

    # City selection
    parser.add_argument("--all-cities", action="store_true", help="Include every city in CITIES")
    parser.add_argument("--only", type=str, help="Comma list of city keys (e.g., miami,nyc,chicago)")
    parser.add_argument("--chicago", action="store_true")
    parser.add_argument("--nyc", action="store_true")
    parser.add_argument("--philly", action="store_true")
    parser.add_argument("--kc", action="store_true")
    parser.add_argument("--slc", action="store_true")

    args, unknown = parser.parse_known_args()

    # --all means both
    if args.all:
        args.all_cities = True
        args.all_delivery = True

    # Delivery defaults: if nothing specified, send both
    explicit = args.email or args.slack or args.all_delivery
    send_email_flag = args.email or args.all_delivery or (not explicit)
    send_slack_flag = args.slack or args.all_delivery or (not explicit)

    # Cities
    sel = _resolve_city_selection(args, unknown)

    # Labels
    today_dt = date.today()
    tomorrow_dt = today_dt + timedelta(days=1)
    if args.weekend:
        delta_to_sat = (5 - today_dt.weekday()) % 7
        sat_dt = today_dt + timedelta(days=delta_to_sat)
        sun_dt = sat_dt + timedelta(days=1)
        labels = ["SATURDAY", "SUNDAY"]
        label_dates = [sat_dt, sun_dt]
    elif args.tomorrow:
        labels = [tomorrow_dt.strftime("%A").upper()]
        label_dates = [tomorrow_dt]
    else:
        labels = ["REST OF TODAY", "TODAY"]
        label_dates = [today_dt]

    # Chicago season gate
    if "chicago" in sel and not any(in_season(d) for d in label_dates):
        if sel == ["chicago"]:
            print("[info] Chicago out of season; no message sent.")
            return 0
        sel = [k for k in sel if k != "chicago"]

    # Build entries
    entries = []
    for key in sel:
        # Choose concrete "today" label that actually exists for marine products
        if labels == ["REST OF TODAY", "TODAY"]:
            if CITIES[key]["type"] == "marine":
                mt = fetch_city_marine_text(CITIES[key].get("marine_zones") or [])
                use_label = _pick_present_day_label(mt) if mt else "TODAY"
            else:
                use_label = "TODAY"
            entries_labels = [use_label]
        else:
            entries_labels = labels

        for lab in entries_labels:
            meta = CITIES[key]
            if key == "chicago":
                e = chicago_forecast(lab)
            else:
                if meta["type"] == "marine":
                    e = marine_city_forecast(key, lab)
                else:
                    e = grid_city_forecast(key, lab)
            entries.append(e)

    # Slack text
    lines = [
        format_slack_line_city(
            e["prefix"],
            e["city"],
            e["label"],
            e["rating"],
            e["wind_line"],
            e["waves_line"],
            e["sky_line"],
            e["sailing"],
            None if e["sailing"] else pick_suggestion(e["city"], e["sky_line"]),
        )
        for e in entries
    ]
    slack_text = "\n".join(lines) if lines else "No data."

    # Email
    try:
        date_str = today_dt.strftime("%a %b %-d, %Y")
    except Exception:
        date_str = today_dt.strftime("%a %b %d, %Y")
    subject = "Sailing Quick Hits — Multi-City"
    text_fallback = "\n".join(f"{e['prefix']} {e['city']} — {e['quick']}" for e in entries)
    html = build_email_html(entries, date_str)

    # Send
    if send_email_flag:
        send_email_html(subject, html, text_fallback)
    if send_slack_flag:
        post_slack(slack_text)

    # Print once
    print(text_fallback)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())