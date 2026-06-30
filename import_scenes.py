#!/usr/bin/python3
"""Import scenes from Companion config MQTT triggers into calcontrol."""
import json
import urllib.request

BASE = 'http://localhost:8082'

def api(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={'Content-Type': 'application/json'} if data else {})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

# Extracted from MacMini_2026-06-29-2033.companionconfig
# Only MQTT publish actions (action="publish"), skipping disabled ones
SCENES = [
    {
        'name': 'Audio Before Meeting',
        'actions': [
            ('clearone/10/PRESET/2/set', '0'),
            ('clearone/10/PRESET/1/set', '1'),
            ('clearone/10/MUTE/1/O/set', '0'),
            ('clearone/H2/MUTE/2/J/set', '0'),
            ('clearone/H2/MUTE/3/J/set', '0'),
            ('clearone/H2/MUTE/4/J/set', '0'),
            ('clearone/H2/MUTE/5/O/set', '0'),
            ('clearone/H2/MUTE/6/O/set', '0'),
            ('clearone/10/MUTE/1/M/set', '0'),
            ('clearone/10/MUTE/2/M/set', '0'),
            ('clearone/H2/MUTE/A/P/set', '0'),
            ('clearone/H2/MUTE/B/P/set', '0'),
            ('clearone/H2/MUTE/C/P/set', '0'),
            ('clearone/H2/MUTE/D/P/set', '0'),
            ('clearone/H2/MUTE/E/P/set', '0'),
            ('clearone/10/MUTE/1/F/set', '1'),
            ('clearone/10/MUTE/5/M/set', '1'),
            ('clearone/10/MUTE/6/M/set', '1'),
            ('clearone/10/MUTE/9/L/set', '1'),
            ('clearone/10/MUTE/10/L/set', '1'),
            ('clearone/H2/MUTE/G/P/set', '0'),
            ('clearone/H2/MUTE/H/P/set', '0'),
            ('clearone/H2/GAIN/A/P/set', '0 A'),
            ('clearone/H2/GAIN/B/P/set', '0 A'),
            ('clearone/H2/GAIN/C/P/set', '0 A'),
            ('clearone/H2/GAIN/D/P/set', '0 A'),
            ('clearone/H2/GAIN/E/P/set', '0 A'),
            ('clearone/H2/GAIN/G/P/set', '0 A'),
            ('clearone/H2/GAIN/H/P/set', '0 A'),
            ('clearone/H2/GAIN/5/O/set', '0 A'),
            ('clearone/H2/GAIN/6/O/set', '0 A'),
            ('clearone/10/GAIN/1/F/set', '0 A'),
            ('clearone/H2/MUTE/8/M/set', '0'),
            ('clearone/H2/GMODE/1/set', '1'),
            ('clearone/H2/GMODE/3/set', '1'),
            ('clearone/H2/GMODE/4/set', '1'),
            ('clearone/H2/GMODE/5/set', '1'),
            ('clearone/H2/GMODE/6/set', '1'),
            ('tuya/stage/1/set', 'on'),
        ],
    },
    {
        'name': 'Audio After Meeting',
        'actions': [
            ('clearone/10/PRESET/2/set', '0'),
            ('clearone/10/PRESET/1/set', '1'),
            ('clearone/H2/MUTE/1/J/set', '1'),
            ('clearone/H2/MUTE/2/J/set', '1'),
            ('clearone/H2/MUTE/3/J/set', '1'),
            ('clearone/H2/MUTE/4/J/set', '1'),
            ('clearone/10/MUTE/1/O/set', '1'),
        ],
    },
    {
        'name': 'Child Minding Unmute',
        'actions': [
            ('clearone/H2/MUTE/2/J/set', '0'),
            ('clearone/H2/MUTE/1/J/set', '0'),
            ('clearone/H2/MUTE/3/J/set', '0'),
        ],
    },
    {
        'name': 'Mute Audience',
        'actions': [
            ('clearone/10/MUTE/1/M/set', '1'),
            ('clearone/10/MUTE/2/M/set', '1'),
        ],
    },
    {
        'name': 'UnMute Audience',
        'actions': [
            ('clearone/10/MUTE/1/M/set', '0'),
            ('clearone/10/MUTE/2/M/set', '0'),
        ],
    },
    {
        'name': 'Lights When Alarm Disarmed',
        'actions': [
            ('tuya/main_hall/1/set', 'on'),
            ('tuya/main_hall/2/set', 'on'),
            ('tuya/main_hall/3/set', 'on'),
            ('tuya/main_hall/4/set', 'on'),
            ('tuya/fost/3/set', 'on'),
            ('tuya/fost/4/set', 'on'),
        ],
    },
    {
        'name': 'Lights When Alarm Armed',
        'actions': [
            ('tuya/main_hall/1/set', 'off'),
            ('tuya/main_hall/2/set', 'off'),
            ('tuya/main_hall/3/set', 'off'),
            ('tuya/main_hall/4/set', 'off'),
            ('tuya/fost/1/set', 'off'),
            ('tuya/fost/2/set', 'off'),
            ('tuya/fost/3/set', 'off'),
            ('tuya/fost/4/set', 'off'),
        ],
    },
    {
        'name': 'Lights at Sunset',
        'actions': [
            ('tuya/fost/1/set', 'on'),
            ('tuya/fost/2/set', 'on'),
        ],
    },
    {
        'name': 'AV System Powered On',
        'actions': [
            ('clearone/H2/MTRX/E/P/set', 'G P 1'),
            ('clearone/H2/MTRX/E/P/set', 'H P 1'),
            ('clearone/H2/MTRX/D/P/set', 'G P 1'),
            ('clearone/H2/MTRX/D/P/set', 'H P 1'),
            ('clearone/10/MUTE/1/O/set', '1'),
            ('clearone/H2/MUTE/2/J/set', '1'),
            ('clearone/H2/MUTE/1/J/set', '1'),
            ('clearone/H2/MUTE/3/J/set', '1'),
            ('clearone/H2/MUTE/4/J/set', '1'),
        ],
    },
    {
        'name': 'Camp Clock Off',
        'actions': [
            ('hasp/plate/command/backlight', 'off'),
        ],
    },
]

existing = {s['name'].lower(): s['id'] for s in api('GET', '/api/scenes')}

for scene in SCENES:
    name = scene['name']
    if name.lower() in existing:
        print(f'SKIP (already exists): {name}')
        continue
    result = api('POST', '/api/scenes', {'name': name, 'description': 'Imported from Companion', 'color': '#1a73e8'})
    sid = result['id']
    for order, (topic, payload) in enumerate(scene['actions']):
        api('POST', f'/api/scenes/{sid}/actions', {
            'topic': topic,
            'payload': payload,
            'delay_seconds': 0,
            'action_order': order,
        })
    print(f'Created: {name} ({len(scene["actions"])} actions)')

print('Done.')
