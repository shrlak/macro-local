"""Minimal CalDAV client (RFC 4791) for iCloud, Fastmail, Nextcloud and similar. Standard library only."""
import base64
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

NS = {"d": "DAV:", "c": "urn:ietf:params:xml:ns:caldav"}
XML_HEAD = '<?xml version="1.0" encoding="utf-8"?>'


class CalDAVError(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None  # we follow redirects ourselves so PROPFIND/REPORT keep their method and body


class Client:
    def __init__(self, url, user, password, timeout=30):
        self.base = url.strip()
        self.auth = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
        self.timeout = timeout
        self.opener = urllib.request.build_opener(_NoRedirect)

    def request(self, method, url, body=None, headers=None, depth=None):
        """-> (status, headers, bytes). Redirects are followed; HTTP errors are returned, not raised."""
        h = {"Authorization": self.auth, "User-Agent": "MacroLocal"}
        if body is not None:
            h["Content-Type"] = "application/xml; charset=utf-8"
        if depth is not None:
            h["Depth"] = str(depth)
        h.update(headers or {})
        data = body.encode() if isinstance(body, str) else body
        for _ in range(6):
            try:
                with self.opener.open(urllib.request.Request(url, data=data, method=method, headers=h), timeout=self.timeout) as r:
                    return r.status, dict(r.headers), r.read()
            except urllib.error.HTTPError as e:
                if e.code in (301, 302, 307, 308) and e.headers.get("Location"):
                    url = urllib.parse.urljoin(url, e.headers["Location"])
                    continue
                if e.code == 401:
                    raise CalDAVError("Authentication failed. Check the username and use an app-specific password.")
                return e.code, dict(e.headers), e.read()
            except urllib.error.URLError as e:
                raise CalDAVError(f"Cannot reach {url}: {e.reason}")
        raise CalDAVError("Too many redirects")

    def _multistatus(self, method, url, body, depth):
        st, hdr, data = self.request(method, url, body, depth=depth)
        if st not in (200, 207):
            raise CalDAVError(f"{method} {url} failed with HTTP {st}")
        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            raise CalDAVError("Server returned invalid XML")
        for r in root.findall("d:response", NS):
            href = urllib.parse.urljoin(url, r.findtext("d:href", "", NS))
            for ps in r.findall("d:propstat", NS):
                if " 200 " in (ps.findtext("d:status", "", NS) + " "):
                    yield href, ps.find("d:prop", NS)

    # ---- discovery
    def discover(self):
        """-> [{'href': absolute calendar URL, 'name': display name}] of calendars that hold events."""
        def first_href(url, prop_xml, path):
            body = f'{XML_HEAD}<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:prop>{prop_xml}</d:prop></d:propfind>'
            for _, prop in self._multistatus("PROPFIND", url, body, 0):
                el = prop.find(path, NS)
                if el is not None and el.text:
                    return urllib.parse.urljoin(url, el.text.strip())
            return None
        home = None
        principal = first_href(self.base, "<d:current-user-principal/>", "d:current-user-principal/d:href")
        if principal:
            home = first_href(principal, "<c:calendar-home-set/>", "c:calendar-home-set/d:href")
        cals = self._calendars(home or self.base)
        if not cals:
            raise CalDAVError("No event calendars found on this account")
        return cals

    def _calendars(self, home):
        body = (f'{XML_HEAD}<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:prop><d:resourcetype/><d:displayname/>'
                '<c:supported-calendar-component-set/></d:prop></d:propfind>')
        out = []
        for href, prop in self._multistatus("PROPFIND", home, body, 1):
            if prop.find("d:resourcetype/c:calendar", NS) is None:
                continue
            comps = [c.get("name") for c in prop.findall("c:supported-calendar-component-set/c:comp", NS)]
            if comps and "VEVENT" not in comps:
                continue  # reminders / task lists
            out.append({"href": href, "name": prop.findtext("d:displayname", "", NS) or href.rstrip("/").rsplit("/", 1)[-1]})
        return out

    # ---- events
    def fetch(self, cal_href, since):
        """Events overlapping [since, forever). since: 'YYYY-MM-DD'. -> [{'href','etag','ics'}]"""
        body = (f'{XML_HEAD}<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:prop><d:getetag/><c:calendar-data/></d:prop>'
                f'<c:filter><c:comp-filter name="VCALENDAR"><c:comp-filter name="VEVENT"><c:time-range start="{since.replace("-", "")}T000000Z"/>'
                '</c:comp-filter></c:comp-filter></c:filter></c:calendar-query>')
        out = []
        for href, prop in self._multistatus("REPORT", cal_href, body, 1):
            text = prop.findtext("c:calendar-data", "", NS)
            if text:
                out.append({"href": href, "etag": prop.findtext("d:getetag", "", NS), "ics": text})
        return out

    def put(self, href, text, etag=None):
        """Create (etag None) or update (If-Match) an event resource. -> new etag ('' if the server sent none)."""
        h = {"Content-Type": "text/calendar; charset=utf-8", "If-Match": etag} if etag else \
            {"Content-Type": "text/calendar; charset=utf-8", "If-None-Match": "*"}
        st, hdr, _ = self.request("PUT", href, text, headers=h)
        if st == 412:
            raise CalDAVError("The event changed on the server; it will be refreshed on the next sync")
        if st not in (200, 201, 204):
            raise CalDAVError(f"PUT failed with HTTP {st}")
        return next((v for k, v in hdr.items() if k.lower() == "etag"), "")

    def delete(self, href, etag=None):
        st, _, _ = self.request("DELETE", href, headers={"If-Match": etag} if etag else {})
        if st not in (200, 204, 404):
            raise CalDAVError(f"DELETE failed with HTTP {st}")
