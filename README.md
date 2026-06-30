# mqtt-scheduler

MQTT Scheduler watches a Google Calendar and automatically publishes MQTT messages at the start and end times of calendar events. Each event's description lists **scenes** to run — a scene is a named set of MQTT topic/payload pairs defined in a small web UI. A cron-driven poller wakes every 5 minutes, sleeps to the exact fire time, and publishes the messages.

Originally built to drive church AV/lighting/HVAC automation from calendar invites, but it's generic — any MQTT broker, any topics/payloads.

## Features

- Web UI to define **Scenes** (groups of MQTT topic/payload actions, with optional per-action delay and ordering)
- **Macros** — named groups of scene triggers (with their own offsets) that expand from a single `MACRO:Name` line in a calendar description
- Fires at the **exact** start/end time of the event, not just "sometime in the next 5 minutes"
- **Valid Event Titles** filter, so multiple instances can share one calendar without interfering
- Activity log of everything that's fired
- MQTT broker connection status badge
- Manual "Run" button on any scene for testing

## How it works

1. You define scenes in the web UI — each scene is a name plus a list of MQTT `topic`/`payload` pairs.
2. You add lines to a Google Calendar event's **description** referencing scene names (see format below).
3. A cron job runs `calendar_poller.py` every 5 minutes. It fetches upcoming events, finds any triggers due in the next 5 minutes, sleeps until the *exact* fire time, then publishes the MQTT messages for that scene.
4. Once a trigger fires, its line is marked with `✓` in the calendar description so it never fires twice.

### Calendar event description format

One trigger per line. Lines that don't match the format are ignored, so you can keep other notes in the description too.

| Format | When it runs |
|---|---|
| `START:Sunday Morning` | Exactly at event start time |
| `END:Sunday Shutdown` | Exactly at event end time |
| `-30 START:Pre-service Setup` | 30 minutes *before* event start |
| `+15 END:Cleanup` | 15 minutes *after* event end |
| `-240 START:HVAC Preheat` | 4 hours before event start |

Scene names are **case-insensitive**. Example description:

```
-30 START:HVAC Preheat
START:Sunday Morning
END:Sunday Shutdown
+10 END:HVAC Off
```

### Macros

A macro is a named group of scene triggers — each entry has its own trigger type (START/END), offset in minutes, and scene name. Instead of listing every scene in the calendar event, reference one macro:

```
MACRO:Standard
```

The poller expands this in-place into the macro's individual trigger lines (e.g. `-30 START:HVAC Preheat`, `END:Sunday Shutdown`) directly in the calendar event description the first time it sees the line. Those expanded lines then run and get `✓`'d one by one as normal.

### Valid Event Titles

Settings includes a **Valid Event Titles** list — when set, the poller only processes events whose title exactly matches one of the listed names (case-insensitive); everything else is ignored. Leave it empty to process every event. This lets multiple instances share one Google Calendar, e.g.:

- **Main site** — valid titles: `Sunday Meeting`, `Wednesday Meeting`
- **Camp/secondary site** — valid titles: `Camp Meeting`, `Supper`

### Settings reference

| Setting | Description |
|---|---|
| MQTT Host / Port | Address of your MQTT broker |
| MQTT Username / Password | Leave blank if your broker has no authentication |
| Calendar ID | Google Calendar → Settings → your calendar → Calendar ID |
| Check Ahead (minutes) | How far ahead to look for fire times each cron tick (default 5, should match the cron interval) |
| Max Offset (hours) | Set to the largest offset you use in descriptions (e.g. 4 if you use `-240 START:`) |
| Valid Event Titles | One title per line. Only matching events are processed. Blank = all events. |

## Installation

Tested on a Raspberry Pi (Python 3.9+) but runs anywhere with Python 3 and network access to your MQTT broker.

### 1. Clone and install dependencies

```bash
git clone https://github.com/smaurer3/mqtt-scheduler.git
cd mqtt-scheduler
pip3 install -r requirements.txt
```

### 2. Google Calendar API credentials

1. Create a Google Cloud project and enable the **Google Calendar API**.
2. Create an OAuth 2.0 **Desktop app** client ID, download the JSON, and save it as `client_secrets.json` in the project root (this file is gitignored — never commit it).
3. The first time `calendar_poller.py` runs, it will print an authorization URL. If running headless (e.g. on a Pi over SSH), forward a local port:
   ```bash
   ssh -L 8090:localhost:8090 pi@<your-pi-ip>
   ```
   then open the printed URL in a browser on your machine, grant calendar access, and `token.json` will be saved automatically. It self-refreshes after that.

### 3. Start the web app

```bash
uvicorn main:app --host 0.0.0.0 --port 8082
```

On first run this creates `calcontrol.db` (SQLite) automatically — no manual setup needed. The database file is gitignored, so each install starts with its own empty DB.

Open `http://<host>:8082` and:
- Add scenes and their MQTT actions
- Go to **Settings** and set your MQTT broker host/port, Google Calendar ID, and (optionally) Valid Event Titles

### 4. Run the poller on a schedule

Add a cron entry to run the poller every 5 minutes (matching the default `Check Ahead` setting):

```cron
*/5 * * * * /usr/bin/python3 /path/to/mqtt-scheduler/calendar_poller.py >> /path/to/mqtt-scheduler/poller.log 2>&1
```

### 5. (Optional) Run the web app as a systemd service

A sample unit file is provided in `calcontrol.service`:

```ini
[Unit]
Description=MQTT Scheduler
After=network.target

[Service]
User=pi
Group=pi
WorkingDirectory=/home/pi/calcontrol
ExecStart=/home/pi/.local/bin/uvicorn main:app --host 0.0.0.0 --port 8082
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo cp calcontrol.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now calcontrol
```

## Files

| File | Purpose |
|---|---|
| `main.py` | FastAPI web app — scene/macro/settings CRUD, manual scene fire, MQTT status endpoint |
| `database.py` | SQLite schema and data access layer |
| `calendar_poller.py` | Cron script — polls Google Calendar, expands macros, fires scenes at exact times |
| `static/index.html` | Single-page web UI (Scenes, Macros, Activity Log, Settings, Help) |
| `calcontrol.service` | Example systemd unit for the web app |
| `requirements.txt` | Python dependencies |

Not included (gitignored, created at runtime): `calcontrol.db`, `token.json`, `client_secrets.json`.
