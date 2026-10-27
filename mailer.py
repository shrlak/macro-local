"""IMAP fetch and SMTP send using only the standard library."""
import html
import imaplib
import re
import smtplib
import ssl
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr, parsedate_to_datetime


def _dec(h):
    try:
        return str(make_header(decode_header(h or "")))
    except Exception:
        return h or ""


def html_to_text(h):
    h = re.sub(r"(?is)<(script|style).*?</\1>", "", h)
    h = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", h)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(re.sub(r"<[^>]+>", "", h))).strip()


def parse_message(raw):
    msg = message_from_bytes(raw)
    plain, htmls, atts = [], [], []
    for part in msg.walk():
        if part.is_multipart():
            continue
        name = part.get_filename()
        if name or "attachment" in str(part.get("Content-Disposition", "")):
            atts.append(_dec(name or "attachment"))
            continue
        ct = part.get_content_type()
        if ct in ("text/plain", "text/html"):
            try:
                t = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
            except Exception:
                continue
            (plain if ct == "text/plain" else htmls).append(t)
    body = "\n".join(plain).strip() or html_to_text("\n".join(htmls))
    try:
        date = parsedate_to_datetime(msg["Date"]).astimezone().strftime("%Y-%m-%dT%H:%M")
    except Exception:
        date = ""
    return {"message_id": (msg["Message-ID"] or "").strip(), "subject": _dec(msg["Subject"]) or "(no subject)",
            "from": _dec(msg["From"]), "to": _dec(msg["To"]), "cc": _dec(msg["Cc"]), "date": date,
            "in_reply_to": (msg["In-Reply-To"] or "").strip(), "body": body, "attachments": atts}


def fetch_new(cfg, last_uid=0, limit=50, connect=None):
    """Return ([(uid, parsed_message)], newest_uid). Reads INBOX without marking messages read."""
    if connect is None:
        port = int(cfg.get("imap_port") or 993)
        connect = (lambda: imaplib.IMAP4_SSL(cfg["imap_host"], port, ssl_context=ssl.create_default_context())) \
            if port != 143 else (lambda: imaplib.IMAP4(cfg["imap_host"], port))
    c = connect()
    try:
        c.login(cfg["username"] or cfg["address"], cfg["password"])
        c.select("INBOX", readonly=True)
        typ, data = c.uid("SEARCH", None, f"UID {last_uid + 1}:*" if last_uid else "ALL")
        uids = sorted(int(u) for u in (data[0] or b"").split())
        uids = [u for u in uids if u > last_uid][-limit:]
        out = []
        for u in uids:
            typ, d = c.uid("FETCH", str(u), "(BODY.PEEK[])")
            if typ == "OK" and d and isinstance(d[0], tuple):
                out.append((u, parse_message(d[0][1])))
        return out, (uids[-1] if uids else last_uid)
    finally:
        try:
            c.logout()
        except Exception:
            pass


def build_message(cfg, to, subject, body, cc="", in_reply_to="", references=""):
    m = EmailMessage()
    m["From"] = f'{cfg.get("name", "")} <{cfg["address"]}>'.strip() if cfg.get("name") else cfg["address"]
    m["To"], m["Subject"] = to, subject
    if cc:
        m["Cc"] = cc
    m["Date"] = formatdate(localtime=True)
    m["Message-ID"] = make_msgid(domain=cfg["address"].split("@")[-1])
    if in_reply_to:
        m["In-Reply-To"] = in_reply_to
        m["References"] = (references + " " + in_reply_to).strip()
    m.set_content(body)
    return m


def send(cfg, to, subject, body, cc="", in_reply_to="", smtp_ssl=None, smtp_plain=None):
    m = build_message(cfg, to, subject, body, cc, in_reply_to)
    port = int(cfg.get("smtp_port") or 587)
    ctx = ssl.create_default_context()
    if cfg.get("smtp_security", "starttls" if port != 465 else "ssl") == "ssl":
        s = (smtp_ssl or smtplib.SMTP_SSL)(cfg["smtp_host"], port, context=ctx, timeout=30)
    else:
        s = (smtp_plain or smtplib.SMTP)(cfg["smtp_host"], port, timeout=30)
        if cfg.get("smtp_security") != "none":
            s.starttls(context=ctx)
    try:
        s.login(cfg["username"] or cfg["address"], cfg["password"])
        s.send_message(m, to_addrs=[a for _, a in map(parseaddr, (to + "," + cc).split(",")) if a])
    finally:
        try:
            s.quit()
        except Exception:
            pass
    return m
