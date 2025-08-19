from typing import Optional, Tuple

SEVERE_WORDS = {"hazard", "warning", "gale", "storm", "hurricane", "hvy freezing spray"}

def is_severe(text: Optional[str]) -> bool:
    return bool(text) and any(k in text.lower() for k in SEVERE_WORDS)

def pick_weather_emoji(sailing: bool, rating: int, sky: Optional[str],
                       waves: Optional[Tuple[float,float]], wind_rng: Optional[Tuple[int,int]],
                       hazards_text: Optional[str], temp_f: Optional[int], is_non_sailing: bool) -> str:
    s = (sky or "").lower()
    # Priority: severe -> high waves -> rain -> windy (bad) -> cloudy -> sunny -> freezing (non-sailing)
    if is_severe(hazards_text or s):
        return "❌"
    if waves and max(waves) > 4.0 and sailing:
        return "🌊"
    if any(k in s for k in ["rain","shower","thunder","storm","drizzle","t-storm"]):
        return "🌧"
    if wind_rng and rating < 7 and (wind_rng[1] >= 20):
        return "💨"
    if any(k in s for k in ["cloud","overcast"]):
        return "🌥"
    if any(k in s for k in ["sunny","clear","mostly sunny","mostly clear"]):
        return "☀"
    if is_non_sailing and (temp_f is not None) and temp_f < 35:
        return "🥶"
    return "🌥" if "cloud" in s else "☀"

def compose_prefix_emoji(sailing: bool, rating: int, weather_emoji: str) -> str:
    return f"⛵ {weather_emoji}" if sailing and rating >= 6 else weather_emoji