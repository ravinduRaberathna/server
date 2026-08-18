import os
from aiohttp import web
import socketio

sio = socketio.AsyncServer(
    async_mode='aiohttp',
    cors_allowed_origins='*'
)

app = web.Application()
sio.attach(app)

async def index(request):
    return web.json_response({
        "status": "online",
        "message": "🚀 Nexus Arcade Backend Live (Daam 3D + Tank Arena 4P)"
    })

app.router.add_get('/', index)

# Stores
daam_rooms = {}
tank_rooms = {}

TANK_COLORS = [
    {"id": 0, "color": "#00f0ff", "name": "BLUE UNIT"},
    {"id": 1, "color": "#ff0055", "name": "RED UNIT"},
    {"id": 2, "color": "#00ff88", "name": "GREEN UNIT"},
    {"id": 3, "color": "#ffb700", "name": "GOLD UNIT"}
]

@sio.event
async def connect(sid, environ):
    print(f"🟢 Connected: {sid}")

# ==========================================
# ♟️ DAAM 3D EVENTS (1v1)
# ==========================================
@sio.event
async def join_room(sid, data):
    raw_room_id = data.get("roomId", "")
    player_name = data.get("playerName", "Player")
    room_id = str(raw_room_id).strip().lower()

    if not room_id:
        return

    if room_id not in daam_rooms:
        daam_rooms[room_id] = {
            "id": room_id,
            "players": [],
            "currentTurn": "red"
        }

    room = daam_rooms[room_id]
    existing_player = next((p for p in room["players"] if p["id"] == sid), None)

    if len(room["players"]) >= 2 and not existing_player:
        await sio.emit("room_full", to=sid)
        return

    await sio.enter_room(sid, room_id)

    if existing_player:
        assigned_color = existing_player["color"]
    else:
        assigned_color = "white" if len(room["players"]) == 1 and room["players"][0]["color"] == "red" else "red"
        room["players"].append({
            "id": sid,
            "name": player_name,
            "color": assigned_color
        })

    await sio.emit("player_assigned", {"color": assigned_color, "roomId": room_id}, to=sid)
    await sio.emit("room_update", room, room=room_id)

@sio.event
async def make_move(sid, data):
    room_id = str(data.get("roomId", "")).strip().lower()
    move_data = data.get("moveData", {})
    await sio.emit("opponent_moved", move_data, room=room_id, skip_sid=sid)

# ==========================================
# 🛡️ TANK ARENA 4-PLAYER EVENTS
# ==========================================
@sio.event
async def join_tank_room(sid, data):
    raw_room_id = data.get("roomId", "")
    player_name = data.get("playerName", "Pilot")
    room_id = str(raw_room_id).strip().lower()

    if not room_id:
        return

    if room_id not in tank_rooms:
        tank_rooms[room_id] = {
            "id": room_id,
            "players": [],
            "matchStarted": False
        }

    room = tank_rooms[room_id]
    existing_player = next((p for p in room["players"] if p["id"] == sid), None)

    if len(room["players"]) >= 4 and not existing_player:
        await sio.emit("tank_room_full", to=sid)
        return

    await sio.enter_room(sid, room_id)

    if existing_player:
        slot_idx = existing_player["slot"]
    else:
        used_slots = [p["slot"] for p in room["players"]]
        available_slots = [i for i in range(4) if i not in used_slots]
        slot_idx = available_slots[0] if available_slots else 0

        player_info = {
            "id": sid,
            "name": player_name,
            "slot": slot_idx,
            "color": TANK_COLORS[slot_idx]["color"],
            "unitName": TANK_COLORS[slot_idx]["name"]
        }
        room["players"].append(player_info)

    player_data = next(p for p in room["players"] if p["id"] == sid)

    await sio.emit("tank_player_assigned", {
        "slot": player_data["slot"],
        "color": player_data["color"],
        "unitName": player_data["unitName"],
        "roomId": room_id
    }, to=sid)

    await sio.emit("tank_room_update", room, room=room_id)
    print(f"🛡️ Tank Player {sid} joined Room '{room_id}' as Slot {slot_idx}")

@sio.event
async def sync_tank_state(sid, data):
    room_id = str(data.get("roomId", "")).strip().lower()
    tank_data = data.get("tankData", {})
    await sio.emit("tank_state_updated", {
        "senderId": sid,
        "tankData": tank_data
    }, room=room_id, skip_sid=sid)

@sio.event
async def tank_fire_bullet(sid, data):
    room_id = str(data.get("roomId", "")).strip().lower()
    bullet_data = data.get("bulletData", {})
    await sio.emit("bullet_spawned", bullet_data, room=room_id, skip_sid=sid)

@sio.event
async def sync_core_damage(sid, data):
    room_id = str(data.get("roomId", "")).strip().lower()
    damage_info = data.get("damageInfo", {})
    await sio.emit("core_damaged", damage_info, room=room_id, skip_sid=sid)

# ==========================================
# DISCONNECT
# ==========================================
@sio.event
async def disconnect(sid):
    print(f"🔴 Disconnected: {sid}")

    # Clean Daam rooms
    to_remove_daam = []
    for r_id, r in daam_rooms.items():
        r["players"] = [p for p in r["players"] if p["id"] != sid]
        if len(r["players"]) == 0:
            to_remove_daam.append(r_id)
        else:
            await sio.emit("room_update", r, room=r_id)

    for r_id in to_remove_daam:
        del daam_rooms[r_id]

    # Clean Tank rooms
    to_remove_tank = []
    for r_id, r in tank_rooms.items():
        r["players"] = [p for p in r["players"] if p["id"] != sid]
        if len(r["players"]) == 0:
            to_remove_tank.append(r_id)
        else:
            await sio.emit("tank_room_update", r, room=r_id)

    for r_id in to_remove_tank:
        del tank_rooms[r_id]

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    web.run_app(app, host='0.0.0.0', port=port)