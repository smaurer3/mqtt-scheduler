#!/usr/bin/python3
"""Church Calendar MQTT Automation Poller
Cron: */5 * * * * /usr/bin/python3 /home/pi/calcontrol/calendar_poller.py

Fires at exact start/end times: collects all pending triggers in the next
check_ahead window, sleeps to each exact moment, then fires.
"""

import re
import sys
import time
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

import paho.mqtt.publish as mqtt_publish
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BASE = Path(__file__).parent
SCOPES = ['https://www.googleapis.com/auth/calendar.events']
TOKEN_FILE = BASE / 'token.json'
SECRETS_FILE = BASE / 'client_secrets.json'
DB_PATH = BASE / 'calcontrol.db'


def parse_dt(s):
    """Parse RFC3339 datetime to aware datetime (handles trailing Z)."""
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    return datetime.fromisoformat(s)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_settings():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r['key']: r['value'] for r in rows}


def get_macro_by_name(name):
    conn = get_db()
    row = conn.execute("SELECT * FROM macros WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_macro_entries(macro_id, trigger=None):
    conn = get_db()
    if trigger:
        rows = conn.execute(
            "SELECT * FROM macro_entries WHERE macro_id = ? AND trigger = ? ORDER BY entry_order, id",
            (macro_id, trigger)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM macro_entries WHERE macro_id = ? ORDER BY entry_order, id",
            (macro_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_scene_by_name(name):
    conn = get_db()
    row = conn.execute("SELECT * FROM scenes WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_scene_actions(scene_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM scene_actions WHERE scene_id = ? ORDER BY action_order, id",
        (scene_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def log_fired_event(google_event_id, scene_name, status='ok', note=''):
    conn = get_db()
    conn.execute(
        "INSERT INTO fired_events (google_event_id, scene_name, status, note) VALUES (?, ?, ?, ?)",
        (google_event_id, scene_name, status, note)
    )
    conn.commit()
    conn.close()


def get_credentials():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not SECRETS_FILE.exists():
                print(f"ERROR: {SECRETS_FILE} not found.")
                print("Copy client_secrets.json from the Oracle VM:")
                print("  scp recordingshare_oracle_vm:/var/www/recordingshare.com/zoomadmin/client_secrets.json /home/pi/calcontrol/")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(SECRETS_FILE, SCOPES)
            # Headless auth via SSH port forward:
            #   ssh -L 8090:localhost:8090 pi@192.168.10.213  (separate terminal)
            # then visit the printed URL in your Windows browser.
            creds = flow.run_local_server(port=8090, open_browser=False)
        TOKEN_FILE.write_text(creds.to_json())
    return creds


def fire_scene(scene_name, event_id, trigger, mqtt_host, mqtt_port, auth):
    scene = get_scene_by_name(scene_name)
    if not scene:
        print(f"    WARNING: Scene '{scene_name}' not found in database — skipping")
        log_fired_event(event_id, scene_name, status='error', note='Scene not found')
        return

    actions = get_scene_actions(scene['id'])
    if not actions:
        print(f"    WARNING: Scene '{scene_name}' has no actions — skipping")
        return

    for action in actions:
        if action['delay_seconds'] > 0:
            time.sleep(action['delay_seconds'])
        try:
            mqtt_publish.single(
                action['topic'],
                payload=action['payload'],
                hostname=mqtt_host,
                port=mqtt_port,
                auth=auth
            )
            print(f"    MQTT [{trigger}]: {action['topic']} = {action['payload']}")
            log_fired_event(event_id, scene_name, status='ok',
                            note=f"[{trigger}] {action['topic']}={action['payload']}")
        except Exception as e:
            print(f"    ERROR publishing {action['topic']}: {e}")
            log_fired_event(event_id, scene_name, status='error',
                            note=f"[{trigger}] {e}")


def mark_line_done(service, calendar_id, event_id, original_line):
    """Re-fetch event and mark the exact original line with ✓."""
    try:
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        description = event.get('description', '') or ''
        lines = description.splitlines()
        changed = False
        for i, line in enumerate(lines):
            if line.strip() == original_line:
                lines[i] = f'✓ {line.strip()}'
                changed = True
                break
        if changed:
            event['description'] = '\n'.join(lines)
            service.events().update(
                calendarId=calendar_id, eventId=event_id, body=event
            ).execute()
    except Exception as e:
        print(f"    WARNING: Could not update calendar description: {e}")


def expand_macros(service, calendar_id, events):
    """Replace MACRO START/END lines with their constituent trigger lines in-place."""
    for event in events:
        description = event.get('description', '') or ''
        lines = description.splitlines()
        new_lines = []
        changed = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('✓'):
                new_lines.append(line)
                continue
            m = re.match(r'^MACRO:\s*(.+)', stripped, re.IGNORECASE)
            if not m:
                new_lines.append(line)
                continue
            macro_name = m.group(1).strip()
            macro = get_macro_by_name(macro_name)
            if not macro:
                print(f"  WARNING: Macro '{macro_name}' not found — leaving line as-is")
                new_lines.append(line)
                continue
            entries = get_macro_entries(macro['id'])
            if not entries:
                print(f"  WARNING: Macro '{macro_name}' has no entries — skipping line")
                new_lines.append(line)
                continue
            for entry in entries:
                offset = entry['offset_minutes']
                prefix = f"{offset:+d} " if offset != 0 else ""
                new_lines.append(f"{prefix}{entry['trigger']}:{entry['scene_name']}")
            print(f"  Expanded MACRO:{macro_name} → {len(entries)} trigger(s)")
            changed = True

        if changed:
            event['description'] = '\n'.join(new_lines)
            try:
                ev = service.events().get(calendarId=calendar_id, eventId=event['id']).execute()
                ev['description'] = event['description']
                service.events().update(calendarId=calendar_id, eventId=event['id'], body=ev).execute()
            except Exception as e:
                print(f"  WARNING: Could not write macro expansion to calendar: {e}")


def collect_triggers(events, now, check_ahead_dt, valid_titles=None):
    """Scan all events and return pending triggers sorted by fire time.

    Line format (in calendar event description):
        START:Scene Name           fires at event start
        END:Scene Name             fires at event end
        +30 START:Scene Name       fires 30 min after event start
        -15 END:Scene Name         fires 15 min before event end
    """
    triggers = []
    for event in events:
        title = event.get('summary', '').strip()
        if valid_titles and title.lower() not in valid_titles:
            continue  # title not in whitelist — skip

        start_str = event.get('start', {}).get('dateTime')
        end_str = event.get('end', {}).get('dateTime')
        if not start_str:
            continue  # skip all-day events

        start_dt = parse_dt(start_str)
        end_dt = parse_dt(end_str) if end_str else None
        description = event.get('description', '') or ''

        for line in description.splitlines():
            stripped = line.strip()
            if stripped.startswith('✓'):
                continue  # already fired

            # Match optional offset then START/END:scene
            m = re.match(r'^([+-]?\d+)\s+(START|END):\s*(.+)', stripped, re.IGNORECASE)
            if m:
                offset_min = int(m.group(1))
                trigger = m.group(2).upper()
                scene_name = m.group(3).strip()
            else:
                m = re.match(r'^(START|END):\s*(.+)', stripped, re.IGNORECASE)
                if not m:
                    continue
                offset_min = 0
                trigger = m.group(1).upper()
                scene_name = m.group(2).strip()

            base_time = start_dt if trigger == 'START' else end_dt
            if not base_time:
                continue

            fire_time = base_time + timedelta(minutes=offset_min)

            if now <= fire_time <= check_ahead_dt:
                triggers.append({
                    'fire_time': fire_time,
                    'trigger': trigger,
                    'scene_name': scene_name,
                    'offset_min': offset_min,
                    'event_id': event['id'],
                    'event_title': event.get('summary', '(no title)'),
                    'original_line': stripped,  # used to find the line when marking ✓
                })

    triggers.sort(key=lambda t: t['fire_time'])
    return triggers


def main():
    settings = get_settings()
    calendar_id = settings.get('calendar_id', '').strip()
    if not calendar_id:
        print("ERROR: No calendar_id configured. Set it via the web UI at http://192.168.10.213:8082")
        sys.exit(1)

    check_ahead = int(settings.get('check_ahead_minutes', 5))
    max_offset_hours = int(settings.get('max_offset_hours', 4))
    mqtt_host = settings.get('mqtt_host', '192.168.10.1')
    mqtt_port = int(settings.get('mqtt_port', 1883))
    mqtt_user = settings.get('mqtt_user', '').strip() or None
    mqtt_pass = settings.get('mqtt_pass', '').strip() or None
    auth = {'username': mqtt_user, 'password': mqtt_pass} if mqtt_user else None

    now = datetime.now(timezone.utc)
    check_ahead_dt = now + timedelta(minutes=check_ahead)

    valid_titles_raw = settings.get('valid_titles', '').strip()
    valid_titles = [t.strip().lower() for t in valid_titles_raw.splitlines() if t.strip()]

    print(f"{now.strftime('%Y-%m-%d %H:%M:%S')} UTC: Checking calendar (next {check_ahead} min, offset window ±{max_offset_hours}h)")
    if valid_titles:
        print(f"  Valid titles filter: {valid_titles}")

    creds = get_credentials()
    service = build('calendar', 'v3', credentials=creds)

    # Widen the event fetch window to cover the maximum offset in both directions:
    #   time_min: look back max_offset_hours for events with +offset END triggers
    #   time_max: look ahead max_offset_hours for events with -offset START triggers
    time_min = (now - timedelta(hours=max_offset_hours)).isoformat()
    time_max = (now + timedelta(hours=max_offset_hours, minutes=check_ahead)).isoformat()

    result = service.events().list(
        calendarId=calendar_id,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = result.get('items', [])
    print(f"Found {len(events)} event(s) in window")

    expand_macros(service, calendar_id, events)
    triggers = collect_triggers(events, now, check_ahead_dt, valid_titles)
    if not triggers:
        print("No pending triggers.")
        print("Done.")
        return

    print(f"{len(triggers)} trigger(s) to fire:")
    for t in triggers:
        print(f"  {t['fire_time'].astimezone().strftime('%H:%M:%S')} [{t['trigger']}] '{t['scene_name']}' (event: '{t['event_title']}')")

    for t in triggers:
        delay = (t['fire_time'] - datetime.now(timezone.utc)).total_seconds()
        if delay > 0:
            local_time = t['fire_time'].astimezone().strftime('%H:%M:%S')
            print(f"  Waiting {delay:.1f}s until {local_time} to fire [{t['trigger']}] '{t['scene_name']}'...")
            time.sleep(delay)

        print(f"  Firing [{t['trigger']}] '{t['scene_name']}'")
        fire_scene(t['scene_name'], t['event_id'], t['trigger'], mqtt_host, mqtt_port, auth)
        mark_line_done(service, calendar_id, t['event_id'], t['original_line'])

    print("Done.")


if __name__ == '__main__':
    main()
