# Macro Local

A self-hosted desktop app inspired by macro.com. **Docs, Tasks, Chat, Email, Calendar, Video Calls and CRM** in one window,
linked together by `[[wiki links]]` and one search. No AI, no cloud account, no third-party Python packages.

## Install (macOS)
1. Download **MacroLocal.dmg** from the repo's [Releases](../../releases) page.
2. Open it and drag **Macro Local** into **Applications**.
3. First launch only: the app isn't signed with an Apple Developer ID, so macOS asks for approval — right-click the app → **Open**
   (macOS 14 and earlier), or **System Settings → Privacy & Security → Open Anyway** (macOS 15+).

It opens in its own window (Chrome, Edge, Brave or Chromium if installed — otherwise your default browser) and quits when you close it.
Your data lives in `~/.macro-local/` (`macro.db` + `recordings/`); copy that folder to back up or move.
The DMG is built for Apple Silicon by GitHub Actions on every push to `main` (see `.github/workflows/build-dmg.yml`) and published as a Release.

## Updates
The packaged app keeps itself up to date from this repo's GitHub Releases:
- It checks for a newer release shortly after launch and every 6 hours, downloads it in the background, and verifies it
  (size + SHA-256). Nothing is installed while you work.
- A banner offers **Restart & update**; otherwise the update is installed automatically **when you quit**, with a rollback if
  anything goes wrong. Updates the app installs itself don't trigger the first-launch Gatekeeper prompt again.
- Settings → Updates shows the version, lets you check manually, and has a switch to turn automatic updates off.
- Running from source, or from a folder the app can't write to (e.g. straight from the DMG), you just get a download link.
Releases are stamped with their version (`v1.0.<n>`) by CI; builds from source report `dev` and are never nagged.

## Run from source (any OS with Python 3.9+)
    python3 server.py        # or ./start.sh

Flags/env: `--no-window`, `--keep-running`, `--cert/--key`; `MACRO_PORT` (8787), `MACRO_HOST`, `MACRO_HOME`, `MACRO_DB`.

## Connect your Gmail + Google Calendar
Settings → **Google account**. One-time setup (~5 min), because you create your own private Google "app" (no shared secret, nobody else sees your data):
1. Google Cloud Console → create a project.
2. Enable the **Gmail API** and **Google Calendar API**.
3. Google Auth platform → External audience → under **Audience → Test users**, add your own Gmail address (required, otherwise Google shows
   *Error 403: access_denied*). Optionally **Publish app** too: in "Testing" mode Google expires the login every 7 days.
4. Create an OAuth client of type **Desktop app**, paste its Client ID/secret into Macro Local, click **Connect Google**.
   Google warns "hasn't verified this app": Advanced → Go to Macro Local → allow.

You get: Gmail inbox + sent (read, reply in-thread, compose; reading a message here marks it read in Gmail, and Gmail read-state flows back),
and **two-way Google Calendar** (primary calendar pulled every 10 min; events you create/edit/delete here are pushed within a second).
Events imported from an `.ics` file or feed are never written to Google. Per-instance edits of a recurring event are not synced.
Don't want to set up Google Cloud? Use the **IMAP preset** for Gmail below with an app password (mail only; add your calendar via its secret iCal address).

## Connect Apple Calendar (iCloud) or any CalDAV calendar — two-way
Settings → **Apple Calendar (iCloud) & other CalDAV**. Create an **app-specific password** (Apple Account → Sign-In and Security →
App-Specific Passwords), then enter your Apple ID email + that password and click Connect (presets for iCloud, Fastmail, Nextcloud).
Pick which calendars to sync and which one receives new events. Pulled every 10 min; edits you make here are pushed immediately,
and alarms/attendees set in Apple Calendar are preserved. "New events go to" lets you choose Google, iCloud/CalDAV, or local only.
Read-only **iCal/webcal feed URLs** (Outlook, public Apple calendars, schedules) are under *Calendar subscriptions*.

## Features
- **Email** – real IMAP/SMTP. Settings → pick a preset (Gmail, Outlook, iCloud, Yahoo) or enter any server. Gmail/iCloud/Yahoo
  need an *app password*. Inbox auto-syncs every 5 min; read, reply, compose (plain text), Sent folder, and turn any message
  into a CRM contact or a task. Messages are read with `BODY.PEEK` so your server's read-state is untouched; attachments are listed, not downloaded.
- **Calendar** – month and agenda views, all-day and recurring events (daily/weekly/monthly/yearly), 10-minute reminders (desktop
  notifications), `.ics` import/export, and subscription to Google/Outlook/any **iCal feed URL** (read-only, refreshed every 30 min).
  Events from a feed are overwritten on refresh; edit those in the source calendar.
- **Calls** – peer-to-peer WebRTC video/audio with screen sharing, in-app audio **recording** (saved to the call), and notes with
  `[[links]]`. "Add video call link" on any event creates a call and puts the join link in the location. The server only relays signaling.
- **Docs / Tasks / CRM / Chat** – `[[Title]]` backlinks, drag-and-drop kanban for tasks and deals, contacts, companies, channels
  (hover a message → "→ task").
- **Search** (`/`) across every item and chat message.

## Using it with other people / devices
Local use needs nothing. To let others on your network join calls or share the workspace:

    MACRO_HOST=0.0.0.0 python3 server.py --cert cert.pem --key key.pem

Browsers only allow camera/microphone on `localhost` or **https**, so other machines need a certificate
(e.g. `openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 365 -subj /CN=<your-ip>`; or put it behind Tailscale/Caddy).
There are **no user accounts**: anyone who can reach the server has full access, so expose it only on a trusted network.
Calls use Google's public STUN server for NAT discovery (change `iceServers` in `static/index.html` to self-host); there is no TURN relay,
so calls between strict NATs can fail.

## Security notes
Email credentials are stored in plaintext in `macro.db` (file mode 600 on Unix) – use app passwords, and keep the folder private.

## Develop
`python3 tests/e2e/serve.py &` then `node tests/e2e/full.test.js` runs a Playwright pass over every feature in a real browser
(docs/links, tasks, chat, CRM, IMAP/SMTP email, calendar + recurrence + .ics + feeds + reminders, calls + recording, search, PWA, mobile).
`python3 -m unittest discover -s tests` (ICS parsing/recurrence/patching, IMAP/SMTP, Google OAuth/Gmail/Calendar and CalDAV flows against fakes, API, signaling, recordings).

## Not included
Real-time collaborative editing, user accounts/permissions, Microsoft OAuth (use IMAP app passwords/iCal feeds), Google Contacts sync,
phone-number calling/PSTN, automatic call transcription, email attachments download/HTML rendering, two-way calendar sync.

## Publishing a release (maintainers)
The DMG can only be built on macOS, so GitHub Actions builds it: every push to `main` runs the tests, builds `MacroLocal.app`,
wraps it in `MacroLocal.dmg`, and attaches it to a new GitHub Release (`v1.0.<run number>`). You can also run the
*Build macOS DMG* workflow by hand from the Actions tab.
