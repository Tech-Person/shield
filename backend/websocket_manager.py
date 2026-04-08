import logging
from typing import Dict, Set
from fastapi import WebSocket
import json

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.channel_subscribers: Dict[str, Set[str]] = {}
        self.dm_subscribers: Dict[str, Set[str]] = {}
        self.voice_participants: Dict[str, Set[str]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"User {user_id} connected via WebSocket")

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)
        for channel_id in list(self.channel_subscribers.keys()):
            self.channel_subscribers[channel_id].discard(user_id)
        for dm_id in list(self.dm_subscribers.keys()):
            self.dm_subscribers[dm_id].discard(user_id)
        for voice_id in list(self.voice_participants.keys()):
            self.voice_participants[voice_id].discard(user_id)
        logger.info(f"User {user_id} disconnected")

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

    def leave_voice(self, user_id: str, channel_id: str):
        if channel_id in self.voice_participants:
            self.voice_participants[channel_id].discard(user_id)

    def get_voice_participants(self, channel_id: str) -> Set[str]:
        return self.voice_participants.get(channel_id, set())

    async def send_personal(self, user_id: str, message: dict):
        ws = self.active_connections.get(user_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(user_id)

    async def broadcast_channel(self, channel_id: str, message: dict, exclude: str = None):
        subscribers = self.channel_subscribers.get(channel_id, set())
        for user_id in subscribers:
            if user_id != exclude:
                await self.send_personal(user_id, message)

    async def broadcast_dm(self, conversation_id: str, message: dict, exclude: str = None):
        subscribers = self.dm_subscribers.get(conversation_id, set())
        for user_id in subscribers:
            if user_id != exclude:
                await self.send_personal(user_id, message)

    async def broadcast_to_users(self, user_ids: list, message: dict, exclude: str = None):
        for user_id in user_ids:
            if user_id != exclude:
                await self.send_personal(user_id, message)

    def get_online_users(self) -> set:
        return set(self.active_connections.keys())

    def is_online(self, user_id: str) -> bool:
        return user_id in self.active_connections


manager = ConnectionManager()
