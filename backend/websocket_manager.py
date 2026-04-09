import logging
from typing import Dict, Set, List
from fastapi import WebSocket
import json

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # Support multiple connections per user (multiple tabs/devices)
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.channel_subscribers: Dict[str, Set[str]] = {}
        self.dm_subscribers: Dict[str, Set[str]] = {}
        self.voice_participants: Dict[str, Set[str]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"User {user_id} connected via WebSocket ({len(self.active_connections[user_id])} connections)")

    def disconnect(self, user_id: str, websocket: WebSocket = None):
        if user_id in self.active_connections:
            if websocket:
                # Remove only the specific websocket
                self.active_connections[user_id] = [
                    ws for ws in self.active_connections[user_id] if ws is not websocket
                ]
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                    self._cleanup_user(user_id)
            else:
                # Remove all connections
                del self.active_connections[user_id]
                self._cleanup_user(user_id)
        logger.info(f"User {user_id} disconnected")

    def _cleanup_user(self, user_id: str):
        """Remove user from all subscriptions when fully disconnected"""
        for channel_id in list(self.channel_subscribers.keys()):
            self.channel_subscribers[channel_id].discard(user_id)
        for dm_id in list(self.dm_subscribers.keys()):
            self.dm_subscribers[dm_id].discard(user_id)
        for voice_id in list(self.voice_participants.keys()):
            self.voice_participants[voice_id].discard(user_id)

    def subscribe_channel(self, user_id: str, channel_id: str):
        if channel_id not in self.channel_subscribers:
            self.channel_subscribers[channel_id] = set()
        self.channel_subscribers[channel_id].add(user_id)

    def unsubscribe_channel(self, user_id: str, channel_id: str):
        if channel_id in self.channel_subscribers:
            self.channel_subscribers[channel_id].discard(user_id)

    def subscribe_dm(self, user_id: str, conversation_id: str):
        if conversation_id not in self.dm_subscribers:
            self.dm_subscribers[conversation_id] = set()
        self.dm_subscribers[conversation_id].add(user_id)

    def join_voice(self, user_id: str, channel_id: str):
        if channel_id not in self.voice_participants:
            self.voice_participants[channel_id] = set()
        self.voice_participants[channel_id].add(user_id)
        # Auto-subscribe to the voice channel for state updates
        self.subscribe_channel(user_id, channel_id)

    def leave_voice(self, user_id: str, channel_id: str):
        if channel_id in self.voice_participants:
            self.voice_participants[channel_id].discard(user_id)

    def get_voice_participants(self, channel_id: str) -> Set[str]:
        return self.voice_participants.get(channel_id, set())

    async def send_personal(self, user_id: str, message: dict):
        connections = self.active_connections.get(user_id, [])
        dead = []
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        # Remove dead connections but don't nuke the entire user
        for ws in dead:
            if user_id in self.active_connections:
                self.active_connections[user_id] = [
                    c for c in self.active_connections[user_id] if c is not ws
                ]
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                    self._cleanup_user(user_id)

    async def broadcast_channel(self, channel_id: str, message: dict, exclude: str = None):
        subscribers = self.channel_subscribers.get(channel_id, set())
        for user_id in list(subscribers):
            if user_id != exclude:
                await self.send_personal(user_id, message)

    async def broadcast_dm(self, conversation_id: str, message: dict, exclude: str = None):
        subscribers = self.dm_subscribers.get(conversation_id, set())
        for user_id in list(subscribers):
            if user_id != exclude:
                await self.send_personal(user_id, message)

    async def broadcast_to_users(self, user_ids: list, message: dict, exclude: str = None):
        for user_id in user_ids:
            if user_id != exclude:
                await self.send_personal(user_id, message)

    def get_online_users(self) -> set:
        return set(self.active_connections.keys())

    def is_online(self, user_id: str) -> bool:
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0


manager = ConnectionManager()
