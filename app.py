import os
from aiohttp import web
import socketio

# 1. Native AIOHTTP Async Socket.IO Server Setup
sio = socketio.AsyncServer(
    async_mode='aiohttp',
    cors_allowed_origins='*'
)

app = web.Application()
sio.attach(app)

# Health Check Route
async def index(request):
    return web.json_response({"status": "online", "message": "🚀 3D Daam Python Server Live"})

app.router.add_get('/', index)

rooms = {}

@sio.event
async def connect(sid, environ):
    print(f"🟢 Connected: {sid}")

@sio.event
async def join_room(sid, data):
    raw_room_id = data.get("roomId", "")
    player_name = data.get("playerName", "Player")
    room_id = str(raw_room_id).strip().lower()

    if not room_id:
        return

    if room_id not in rooms:
        rooms[room_id] = {
            "id": room_id,
            "players": [],
            "currentTurn": "red"
        }

    room = rooms[room_id]

    existing_player = next((p for p in room["players"] if p["id"] == sid), None)
    if len(room["players"]) >= 2 and not existing_player:
        await sio.emit("room_full", to=sid)
        return

    await sio.enter_room(sid, room_id)

    if existing_player:
        assigned_color = existing_player["color"]
    else:
        if len(room["players"]) == 1:
            assigned_color = "white" if room["players"][0]["color"] == "red" else "red"
        else:
            assigned_color = "red"

        room["players"].append({
            "id": sid,
            "name": player_name,
            "color": assigned_color
        })

    await sio.emit("player_assigned", {
        "color": assigned_color,
        "roomId": room_id
    }, to=sid)

    await sio.emit("room_update", room, room=room_id)
    print(f"👤 Player {sid} joined room '{room_id}' as {assigned_color}")

@sio.event
async def make_move(sid, data):
    room_id = str(data.get("roomId", "")).strip().lower()
    move_data = data.get("moveData", {})
    await sio.emit("opponent_moved", move_data, room=room_id, skip_sid=sid)

@sio.event
async def disconnect(sid):
    print(f"🔴 Disconnected: {sid}")
    to_remove = []
    for room_id, room in rooms.items():
        room["players"] = [p for p in room["players"] if p["id"] != sid]
        if len(room["players"]) == 0:
            to_remove.append(room_id)
        else:
            await sio.emit("room_update", room, room=room_id)

    for r in to_remove:
        del rooms[r]

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    web.run_app(app, host='0.0.0.0', port=port)