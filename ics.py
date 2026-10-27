"""Minimal iCalendar (RFC 5545) parsing, export and simple recurrence expansion. Stdlib only.

Times are kept as strings: 'YYYY-MM-DD' (all-day), 'YYYY-MM-DDTHH:MM' (floating/local),
or 'YYYY-MM-DDTHH:MM' + 'Z' (UTC).
"""
import calendar
import datetime as dt
import re
import uuid

try:
    from zoneinfo import ZoneInfo
except Exception:  # Python < 3.9
    ZoneInfo = None

WD = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


def unfold(text):
    lines = []
    for l in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if l[:1] in (" ", "\t") and lines:
            lines[-1] += l[1:]
        else:
            lines.append(l)
    return lines


def unescape(v):
    return (v.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",")
            .replace("\\;", ";").replace("\\\\", "\\"))


def escape(v):
    return (str(v or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r", "").replace("\n", "\\n"))


def parse_time(val, params=None, keep_local=False):
    """ICS value -> (string, allday). keep_local: keep a TZID time as wall-clock (recurring events stay DST-correct)."""
    val, params = val.strip(), params or {}
    if re.fullmatch(r"\d{8}", val):
        return f"{val[:4]}-{val[4:6]}-{val[6:]}", True
    m = re.match(r"(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)(\d\d)?(Z)?", val)
    if not m:
        raise ValueError("bad date " + val)
    y, mo, d, h, mi = (int(x) for x in m.groups()[:5])
    d0 = dt.datetime(y, mo, d, h, mi)
    if m.group(7):
        return d0.strftime("%Y-%m-%dT%H:%M") + "Z", False
    tzid = params.get("TZID")
    if tzid and ZoneInfo and not keep_local:
        try:
            u = d0.replace(tzinfo=ZoneInfo(tzid)).astimezone(dt.timezone.utc)
            return u.strftime("%Y-%m-%dT%H:%M") + "Z", False
        except Exception:
            pass
    return d0.strftime("%Y-%m-%dT%H:%M"), False


def to_dt(s):
    """string -> (naive datetime, is_utc, is_allday)."""
    if len(s) == 10:
        return dt.datetime.strptime(s, "%Y-%m-%d"), False, True
    utc = s.endswith("Z")
    return dt.datetime.strptime(s.rstrip("Z"), "%Y-%m-%dT%H:%M"), utc, False


def fmt(d, utc, allday):
    if allday:
        return d.strftime("%Y-%m-%d")
    return d.strftime("%Y-%m-%dT%H:%M") + ("Z" if utc else "")


def parse_ics(text):
    events, cur = [], None
    for line in unfold(text):
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT" and cur is not None:
            ev, cur = cur, None
            if "RECURRENCE-ID" in ev or "DTSTART" not in ev:
                continue  # per-instance overrides are not supported
            try:
                keep = "RRULE" in ev
                start, allday = parse_time(*ev["DTSTART"], keep_local=keep)
                if "DTEND" in ev:
                    end, _ = parse_time(*ev["DTEND"], keep_local=keep)
                    if allday:  # DTEND is exclusive for all-day events
                        end = (dt.datetime.strptime(end, "%Y-%m-%d") - dt.timedelta(days=1)).strftime("%Y-%m-%d")
                        end = max(end, start)
                else:
                    end = start
            except ValueError:
                continue
            events.append({
                "uid": ev.get("UID", ("", ""))[0] or uuid.uuid4().hex,
                "title": unescape(ev.get("SUMMARY", ("", ""))[0]),
                "body": unescape(ev.get("DESCRIPTION", ("", ""))[0]),
                "location": unescape(ev.get("LOCATION", ("", ""))[0]),
                "start": start, "end": end, "allday": "yes" if allday else "no",
                "rrule": ev.get("RRULE", ("", ""))[0],
            })
        elif cur is not None and ":" in line:
            head, _, value = line.partition(":")
            name, *ps = head.split(";")
            params = dict(p.split("=", 1) for p in ps if "=" in p)
            cur.setdefault(name.upper(), (value, params))
    return events


def _months(d, n):
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return d.replace(year=y, month=m, day=min(d.day, calendar.monthrange(y, m)[1]))


def occurrences(start, end, rrule, win_a, win_b):
    """Yield (start, end) strings for occurrences overlapping [win_a, win_b] ('YYYY-MM-DD')."""
    s, utc, allday = to_dt(start)
    e = to_dt(end or start)[0]
    dur = e - s
    a = dt.datetime.strptime(win_a, "%Y-%m-%d")
    b = dt.datetime.strptime(win_b, "%Y-%m-%d") + dt.timedelta(days=1)
    if allday:
        dur += dt.timedelta(days=1)  # inclusive end -> span
    if not rrule:
        if s < b and s + max(dur, dt.timedelta(minutes=1)) > a:
            yield start, end or start
        return
    r = dict(p.split("=", 1) for p in rrule.split(";") if "=" in p)
    freq, interval = r.get("FREQ", ""), max(int(r.get("INTERVAL", 1) or 1), 1)
    count = int(r["COUNT"]) if r.get("COUNT") else None
    until = None
    if r.get("UNTIL"):
        try:
            u, _ = parse_time(r["UNTIL"])
            until = to_dt(u)[0] + (dt.timedelta(days=1) if len(u) == 10 else dt.timedelta())
        except ValueError:
            pass
    byday = [WD.index(x[-2:]) for x in r.get("BYDAY", "").split(",") if x[-2:] in WD]

    def cands():
        i = 0
        while True:
            if freq == "DAILY":
                yield s + dt.timedelta(days=i * interval)
            elif freq == "WEEKLY":
                ws = s - dt.timedelta(days=s.weekday()) + dt.timedelta(weeks=i * interval)
                for wd in sorted(byday or [s.weekday()]):
                    c = ws + dt.timedelta(days=wd)
                    if c >= s:
                        yield c
            elif freq == "MONTHLY":
                yield _months(s, i * interval)
            elif freq == "YEARLY":
                yield _months(s, 12 * i * interval)
            else:
                return
            i += 1

    n = 0
    for c in cands():
        n += 1
        if (count and n > count) or (until and c >= until) or c >= b or n > 5000:
            return
        if c + max(dur, dt.timedelta(minutes=1)) > a:
            yield fmt(c, utc, allday), fmt(c + dur - (dt.timedelta(days=1) if allday else dt.timedelta()), utc, allday)


def _fold(line):
    out = []
    while len(line) > 74:
        out.append(line[:74])
        line = " " + line[74:]
    return out + [line]


def _to_utc(s, tz):
    """Floating wall-clock time in tz -> UTC string; unchanged if unknown/unavailable."""
    if not (tz and ZoneInfo) or len(s) == 10 or s.endswith("Z"):
        return s
    try:
        d = dt.datetime.strptime(s, "%Y-%m-%dT%H:%M").replace(tzinfo=ZoneInfo(tz)).astimezone(dt.timezone.utc)
        return d.strftime("%Y-%m-%dT%H:%M") + "Z"
    except Exception:
        return s


def _stamp(s, prop, end=False):
    d, utc, allday = to_dt(s)
    if allday:
        if end:
            d += dt.timedelta(days=1)
        return f"{prop};VALUE=DATE:{d.strftime('%Y%m%d')}"
    return f"{prop}:{d.strftime('%Y%m%dT%H%M%S')}{'Z' if utc else ''}"


def event_lines(title, body, d, tz=""):
    """SUMMARY/DTSTART/DTEND/LOCATION/DESCRIPTION/RRULE lines for an event. Single timed events are written in UTC
    (when tz is known); recurring ones stay floating so each client keeps the local hour across DST."""
    allday = d.get("allday") == "yes"
    conv = (lambda x: x) if (allday or d.get("rrule")) else (lambda x: _to_utc(x, tz))
    start = d["start"]
    out = [_stamp(conv(start), "DTSTART"), _stamp(conv(d.get("end") or start), "DTEND", end=allday), "SUMMARY:" + escape(title)]
    if d.get("location"):
        out.append("LOCATION:" + escape(d["location"]))
    if body:
        out.append("DESCRIPTION:" + escape(body))
    if d.get("rrule"):
        out.append("RRULE:" + d["rrule"])
    return out


def export_ics(events, name="Macro Local", tz=""):
    now = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:-//{name}//EN", "CALSCALE:GREGORIAN"]
    for ev in events:
        d = ev.get("data", {})
        if not d.get("start"):
            continue
        out += ["BEGIN:VEVENT", f"UID:{d.get('uid') or ev['id'] + '@macro-local'}", f"DTSTAMP:{now}"]
        out += event_lines(ev["title"], ev.get("body", ""), d, tz)
        out.append("END:VEVENT")
    out.append("END:VCALENDAR")
    return "\r\n".join(l for x in out for l in _fold(x)) + "\r\n"


_REPLACED = {"SUMMARY", "DESCRIPTION", "LOCATION", "DTSTART", "DTEND", "DURATION", "RRULE", "DTSTAMP", "LAST-MODIFIED", "SEQUENCE"}


def patch_ics(raw, ev, tz=""):
    """Update the master VEVENT of an existing calendar resource, keeping everything else
    (alarms, attendees, organizer, per-instance overrides, ...). Falls back to a fresh export."""
    lines = unfold(raw)
    blocks, start = [], None
    for i, l in enumerate(lines):
        if l == "BEGIN:VEVENT":
            start = i
        elif l == "END:VEVENT" and start is not None:
            blocks.append((start, i))
            start = None
    master = next(((a, b) for a, b in blocks if not any(l.upper().startswith("RECURRENCE-ID") for l in lines[a:b])), None)
    if not master:
        return export_ics([ev], tz=tz)
    a, b = master
    kept, depth, seq = [], 0, 0
    for l in lines[a + 1:b]:
        if l.startswith("BEGIN:"):
            depth += 1
        elif l.startswith("END:"):
            depth -= 1
        name = l.split(":", 1)[0].split(";")[0].upper()
        if depth == 0 and not l.startswith("END:") and name in _REPLACED:
            if name == "SEQUENCE":
                try:
                    seq = int(l.split(":", 1)[1])
                except ValueError:
                    pass
            continue
        kept.append(l)
    new = event_lines(ev["title"], ev.get("body", ""), ev["data"], tz)
    new += [f"DTSTAMP:{dt.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}", f"SEQUENCE:{seq + 1}"]
    out = lines[:a + 1] + kept + new + lines[b:]
    return "\r\n".join(l for x in out if x for l in _fold(x)) + "\r\n"
