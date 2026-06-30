#!/usr/bin/python3
import time
import socket
from contextlib import asynccontextmanager
from typing import Optional

import paho.mqtt.publish as mqtt_publish
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from database import (
    init_db, get_settings, save_setting,
    get_scenes, get_scene, create_scene, update_scene, delete_scene,
    get_scene_actions, add_action, update_action, delete_action,
    log_fired_event, get_log,
    get_macros, get_macro, create_macro, update_macro, delete_macro,
    get_macro_entries, add_macro_entry, update_macro_entry, delete_macro_entry,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)


# --- Pydantic models ---

class SceneIn(BaseModel):
    name: str
    description: str = ''
    color: str = '#1a73e8'

class ActionIn(BaseModel):
    topic: str
    payload: str = ''
    delay_seconds: float = 0
    action_order: int = 0
    description: str = ''

class MacroIn(BaseModel):
    name: str
    description: str = ''

class MacroEntryIn(BaseModel):
    trigger: str = 'START'
    offset_minutes: int = 0
    scene_name: str
    entry_order: int = 0

class SettingsIn(BaseModel):
    mqtt_host: Optional[str] = None
    mqtt_port: Optional[str] = None
    mqtt_user: Optional[str] = None
    mqtt_pass: Optional[str] = None
    calendar_id: Optional[str] = None
    check_ahead_minutes: Optional[str] = None
    max_offset_hours: Optional[str] = None
    timezone: Optional[str] = None
    valid_titles: Optional[str] = None


# --- MQTT fire helper ---

def _do_fire(scene_id: int, event_id: str = 'manual') -> dict:
    settings = get_settings()
    host = settings.get('mqtt_host', '192.168.10.1')
    port = int(settings.get('mqtt_port', 1883))
    mqtt_user = settings.get('mqtt_user', '').strip() or None
    mqtt_pass = settings.get('mqtt_pass', '').strip() or None
    auth = {'username': mqtt_user, 'password': mqtt_pass} if mqtt_user else None

    scene = get_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail='Scene not found')

    actions = get_scene_actions(scene_id)
    results = []
    for action in actions:
        if action['delay_seconds'] > 0:
            time.sleep(action['delay_seconds'])
        try:
            mqtt_publish.single(
                action['topic'],
                payload=action['payload'],
                hostname=host,
                port=port,
                auth=auth
            )
            results.append({'topic': action['topic'], 'payload': action['payload'], 'status': 'ok'})
            log_fired_event(event_id, scene['name'], status='ok',
                            note=f"{action['topic']}={action['payload']}")
        except Exception as e:
            results.append({'topic': action['topic'], 'payload': action['payload'],
                            'status': 'error', 'error': str(e)})
            log_fired_event(event_id, scene['name'], status='error', note=str(e))

    return {'scene': scene['name'], 'actions': results}


# --- Scene endpoints ---

@app.get('/api/scenes')
def list_scenes():
    scenes = get_scenes()
    for s in scenes:
        s['actions'] = get_scene_actions(s['id'])
    return scenes

@app.post('/api/scenes', status_code=201)
def create_scene_ep(body: SceneIn):
    scene_id = create_scene(body.name, body.description, body.color)
    return {'id': scene_id}

@app.get('/api/scenes/{scene_id}')
def get_scene_ep(scene_id: int):
    scene = get_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail='Scene not found')
    scene['actions'] = get_scene_actions(scene_id)
    return scene

@app.put('/api/scenes/{scene_id}')
def update_scene_ep(scene_id: int, body: SceneIn):
    if not get_scene(scene_id):
        raise HTTPException(status_code=404, detail='Scene not found')
    update_scene(scene_id, body.name, body.description, body.color)
    return {'ok': True}

@app.delete('/api/scenes/{scene_id}')
def delete_scene_ep(scene_id: int):
    if not get_scene(scene_id):
        raise HTTPException(status_code=404, detail='Scene not found')
    delete_scene(scene_id)
    return {'ok': True}

@app.post('/api/scenes/{scene_id}/fire')
def fire_scene_ep(scene_id: int):
    return _do_fire(scene_id)

@app.post('/api/scenes/{scene_id}/duplicate', status_code=201)
def duplicate_scene_ep(scene_id: int):
    scene = get_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail='Scene not found')
    new_id = create_scene(scene['name'] + ' Copy', scene['description'], scene['color'])
    for a in get_scene_actions(scene_id):
        add_action(new_id, a['topic'], a['payload'], a['delay_seconds'], a['action_order'], a.get('description', ''))
    return {'id': new_id}


# --- Action endpoints ---

@app.get('/api/scenes/{scene_id}/actions')
def list_actions(scene_id: int):
    return get_scene_actions(scene_id)

@app.post('/api/scenes/{scene_id}/actions', status_code=201)
def add_action_ep(scene_id: int, body: ActionIn):
    action_id = add_action(scene_id, body.topic, body.payload,
                           body.delay_seconds, body.action_order, body.description)
    return {'id': action_id}

@app.put('/api/scenes/{scene_id}/actions/{action_id}')
def update_action_ep(scene_id: int, action_id: int, body: ActionIn):
    update_action(action_id, body.topic, body.payload,
                  body.delay_seconds, body.action_order, body.description)
    return {'ok': True}

@app.delete('/api/scenes/{scene_id}/actions/{action_id}')
def delete_action_ep(scene_id: int, action_id: int):
    delete_action(action_id)
    return {'ok': True}


# --- Macro endpoints ---

@app.get('/api/macros')
def list_macros():
    macros = get_macros()
    for m in macros:
        m['entries'] = get_macro_entries(m['id'])
    return macros

@app.post('/api/macros', status_code=201)
def create_macro_ep(body: MacroIn):
    macro_id = create_macro(body.name, body.description)
    return {'id': macro_id}

@app.put('/api/macros/{macro_id}')
def update_macro_ep(macro_id: int, body: MacroIn):
    if not get_macro(macro_id):
        raise HTTPException(status_code=404, detail='Macro not found')
    update_macro(macro_id, body.name, body.description)
    return {'ok': True}

@app.post('/api/macros/{macro_id}/duplicate', status_code=201)
def duplicate_macro_ep(macro_id: int):
    macro = get_macro(macro_id)
    if not macro:
        raise HTTPException(status_code=404, detail='Macro not found')
    new_id = create_macro(macro['name'] + ' Copy', macro['description'])
    for e in get_macro_entries(macro_id):
        add_macro_entry(new_id, e['trigger'], e['offset_minutes'], e['scene_name'], e['entry_order'])
    return {'id': new_id}

@app.delete('/api/macros/{macro_id}')
def delete_macro_ep(macro_id: int):
    if not get_macro(macro_id):
        raise HTTPException(status_code=404, detail='Macro not found')
    delete_macro(macro_id)
    return {'ok': True}

@app.get('/api/macros/{macro_id}/entries')
def list_macro_entries(macro_id: int):
    return get_macro_entries(macro_id)

@app.post('/api/macros/{macro_id}/entries', status_code=201)
def add_macro_entry_ep(macro_id: int, body: MacroEntryIn):
    entry_id = add_macro_entry(macro_id, body.trigger.upper(), body.offset_minutes,
                               body.scene_name, body.entry_order)
    return {'id': entry_id}

@app.put('/api/macros/{macro_id}/entries/{entry_id}')
def update_macro_entry_ep(macro_id: int, entry_id: int, body: MacroEntryIn):
    update_macro_entry(entry_id, body.trigger.upper(), body.offset_minutes,
                       body.scene_name, body.entry_order)
    return {'ok': True}

@app.delete('/api/macros/{macro_id}/entries/{entry_id}')
def delete_macro_entry_ep(macro_id: int, entry_id: int):
    delete_macro_entry(entry_id)
    return {'ok': True}


# --- Settings ---

@app.get('/api/settings')
def get_settings_ep():
    s = get_settings()
    s.pop('mqtt_pass', None)
    return s

@app.post('/api/settings')
def save_settings_ep(body: SettingsIn):
    for key, value in body.dict(exclude_none=True).items():
        save_setting(key, value)
    return {'ok': True}


# --- Log ---

@app.get('/api/log')
def get_log_ep(limit: int = 100):
    return get_log(limit)


# --- MQTT status ---

@app.get('/api/mqtt/status')
def mqtt_status():
    settings = get_settings()
    host = settings.get('mqtt_host', '192.168.10.1')
    port = int(settings.get('mqtt_port', 1883))
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        return {'connected': True, 'host': host, 'port': port}
    except Exception as e:
        return {'connected': False, 'host': host, 'port': port, 'error': str(e)}


# --- Static files ---

app.mount('/static', StaticFiles(directory='static'), name='static')

@app.get('/')
def root():
    return FileResponse('static/index.html')
