from typing import List

def format_slack_line_city(prefix_emoji: str, city: str, label: str, rating: int,
                           wind_line: str, waves_line: str, sky_line: str, sailing: bool,
                           suggestion: str | None) -> str:
    if sailing:
        return f"{prefix_emoji} {city} — {label}: {rating}/10. Wind {wind_line}, waves {waves_line}, {sky_line}."
    return f"{prefix_emoji} {city} — {label}: {sky_line or '—'}. {suggestion or ''}".rstrip()

def build_email_html(entries: List[dict], date_str: str) -> str:
    def color(r): return "#16a34a" if r>=8 else ("#eab308" if r>=5 else "#dc2626")
    rows = []
    for e in entries:
        rows.append(f"""
        <tr>
          <td style="padding:8px 10px;border-bottom:1px solid #e5e7eb;">{e['prefix']} {e['city']}</td>
          <td style="padding:8px 10px;border-bottom:1px solid #e5e7eb;">{e['label']}</td>
          <td style="padding:8px 10px;border-bottom:1px solid #e5e7eb;">
            <span style="display:inline-block;padding:2px 8px;border-radius:999px;background:{color(e['rating'])};color:#fff;font-weight:700;">{e['rating']}/10</span>
          </td>
          <td style="padding:8px 10px;border-bottom:1px solid #e5e7eb;">{e['wind_line']}</td>
          <td style="padding:8px 10px;border-bottom:1px solid #e5e7eb;">{e['waves_line']}</td>
          <td style="padding:8px 10px;border-bottom:1px solid #e5e7eb;">{e['sky_line']}</td>
        </tr>""")
    return f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#f6f7fb;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6f7fb;padding:20px 0;">
    <tr><td align="center">
      <table width="880" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;border:1px solid #e5e7eb;">
        <tr><td style="background:#0ea5e9;color:#fff;padding:16px 20px;font-size:18px;font-weight:bold;">
          Sailing Quick Hits — {date_str}
        </td></tr>
        <tr><td style="padding:8px 0 0 0;">
          <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            <thead>
              <tr>
                <th align="left" style="padding:10px;border-bottom:2px solid #e5e7eb;">City</th>
                <th align="left" style="padding:10px;border-bottom:2px solid #e5e7eb;">Day</th>
                <th align="left" style="padding:10px;border-bottom:2px solid #e5e7eb;">Rating</th>
                <th align="left" style="padding:10px;border-bottom:2px solid #e5e7eb;">Wind</th>
                <th align="left" style="padding:10px;border-bottom:2px solid #e5e7eb;">Waves</th>
                <th align="left" style="padding:10px;border-bottom:2px solid #e5e7eb;">Sky</th>
              </tr>
            </thead>
            <tbody>
              {''.join(rows) if rows else '<tr><td colspan="6" style="padding:10px;">No data.</td></tr>'}
            </tbody>
          </table>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""