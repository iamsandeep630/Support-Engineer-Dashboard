"""
Session Store Abstraction supporting In-Memory and Distributed Redis backends.
Enables horizontal scaling of Code Analysis Agent across multiple Uvicorn workers
or ECS Fargate / EC2 instances with automatic TTL eviction.
"""
import os
import json
import time
import logging
import threading
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List

logger = logging.getLogger("session_store")


class ISessionStore(ABC):
    """Abstract interface for session state and pending diff storage."""

    @abstractmethod
    def get_pending_action(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Returns active staged action awaiting human approval."""
        pass

    @abstractmethod
    def save_pending_action(self, session_id: str, action: Dict[str, Any], ttl: int = 3600) -> bool:
        """Saves active staged action with TTL."""
        pass

    @abstractmethod
    def clear_pending_action(self, session_id: str) -> bool:
        """Clears pending action for session."""
        pass

    @abstractmethod
    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """Returns conversational memory history."""
        pass

    @abstractmethod
    def append_history(self, session_id: str, role: str, content: str, ttl: int = 3600) -> None:
        """Appends a turn to conversational history."""
        pass

    @abstractmethod
    def set_stage(self, session_id: str, stage: str, ttl: int = 3600) -> None:
        """Sets HITL stage (STAGE_1_INVESTIGATION or STAGE_2_EXECUTION)."""
        pass

    @abstractmethod
    def get_stage(self, session_id: str) -> str:
        """Gets current HITL stage."""
        pass


class InMemorySessionStore(ISessionStore):
    """Thread-safe In-Memory Session Store with timestamp-based TTL eviction."""

    def __init__(self):
        self._data: Dict[str, Dict[str, Any]] = {}
        self._expires: Dict[str, float] = {}
        self._lock = threading.Lock()

    def _cleanup_expired(self):
        now = time.time()
        expired_keys = [k for k, exp in self._expires.items() if now > exp]
        for k in expired_keys:
            self._data.pop(k, None)
            self._expires.pop(k, None)

    def _ensure_session(self, session_id: str, ttl: int = 3600) -> Dict[str, Any]:
        self._cleanup_expired()
        if session_id not in self._data:
            self._data[session_id] = {
                "pending_action": None,
                "history": [],
                "stage": "STAGE_1_INVESTIGATION"
            }
        self._expires[session_id] = time.time() + ttl
        return self._data[session_id]

    def get_pending_action(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            self._cleanup_expired()
            session = self._data.get(session_id)
            return session.get("pending_action") if session else None

    def save_pending_action(self, session_id: str, action: Dict[str, Any], ttl: int = 3600) -> bool:
        with self._lock:
            session = self._ensure_session(session_id, ttl)
            session["pending_action"] = action
            session["stage"] = "STAGE_1_INVESTIGATION"
            return True

    def clear_pending_action(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._data:
                self._data[session_id]["pending_action"] = None
                self._data[session_id]["stage"] = "STAGE_1_INVESTIGATION"
                return True
            return False

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        with self._lock:
            self._cleanup_expired()
            session = self._data.get(session_id)
            return list(session.get("history", [])) if session else []

    def append_history(self, session_id: str, role: str, content: str, ttl: int = 3600) -> None:
        with self._lock:
            session = self._ensure_session(session_id, ttl)
            session["history"].append({"role": role, "content": content})
            # Bound history to last 20 turns
            if len(session["history"]) > 20:
                session["history"] = session["history"][-20:]

    def set_stage(self, session_id: str, stage: str, ttl: int = 3600) -> None:
        with self._lock:
            session = self._ensure_session(session_id, ttl)
            session["stage"] = stage

    def get_stage(self, session_id: str) -> str:
        with self._lock:
            self._cleanup_expired()
            session = self._data.get(session_id)
            return session.get("stage", "STAGE_1_INVESTIGATION") if session else "STAGE_1_INVESTIGATION"


class RedisSessionStore(ISessionStore):
    """
    Distributed Redis-backed Session Store.
    Stores session metadata with automatic Redis TTL expiration.
    Falls back gracefully to an internal InMemorySessionStore if Redis fails.
    """

    def __init__(self, redis_client=None, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._client = redis_client
        self._fallback = InMemorySessionStore()
        self._redis_available = False

        if self._client is None and self.redis_url:
            self._init_client()

    def _init_client(self):
        try:
            import redis
            self._client = redis.Redis.from_url(
                self.redis_url,
                socket_connect_timeout=1.5,
                socket_timeout=2.0,
                decode_responses=True
            )
            self._client.ping()
            self._redis_available = True
            logger.info(f"[RedisSessionStore] Successfully connected to Redis at {self.redis_url}")
        except Exception as e:
            logger.info(f"[RedisSessionStore] Redis unreachable ({e}). Operating in resilient In-Memory mode.")
            self._redis_available = False

    def get_pending_action(self, session_id: str) -> Optional[Dict[str, Any]]:
        if self._redis_available and self._client:
            try:
                raw = self._client.get(f"caa:session:{session_id}:pending_action")
                if raw:
                    return json.loads(raw)
                return None
            except Exception as e:
                logger.warning(f"Redis get_pending_action error ({e}), reading from fallback.")
        return self._fallback.get_pending_action(session_id)

    def save_pending_action(self, session_id: str, action: Dict[str, Any], ttl: int = 3600) -> bool:
        self._fallback.save_pending_action(session_id, action, ttl)
        if self._redis_available and self._client:
            try:
                self._client.setex(
                    f"caa:session:{session_id}:pending_action",
                    ttl,
                    json.dumps(action)
                )
                self._client.setex(f"caa:session:{session_id}:stage", ttl, "STAGE_1_INVESTIGATION")
                return True
            except Exception as e:
                logger.warning(f"Redis save_pending_action error ({e}), saved to fallback.")
        return True

    def clear_pending_action(self, session_id: str) -> bool:
        self._fallback.clear_pending_action(session_id)
        if self._redis_available and self._client:
            try:
                self._client.delete(f"caa:session:{session_id}:pending_action")
                self._client.set(f"caa:session:{session_id}:stage", "STAGE_1_INVESTIGATION")
                return True
            except Exception as e:
                logger.warning(f"Redis clear_pending_action error: {e}")
        return True

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        if self._redis_available and self._client:
            try:
                raw = self._client.get(f"caa:session:{session_id}:history")
                if raw:
                    return json.loads(raw)
                return []
            except Exception as e:
                logger.warning(f"Redis get_history error ({e}), reading from fallback.")
        return self._fallback.get_history(session_id)

    def append_history(self, session_id: str, role: str, content: str, ttl: int = 3600) -> None:
        self._fallback.append_history(session_id, role, content, ttl)
        if self._redis_available and self._client:
            try:
                history = self.get_history(session_id)
                history.append({"role": role, "content": content})
                if len(history) > 20:
                    history = history[-20:]
                self._client.setex(
                    f"caa:session:{session_id}:history",
                    ttl,
                    json.dumps(history)
                )
            except Exception as e:
                logger.warning(f"Redis append_history error: {e}")

    def set_stage(self, session_id: str, stage: str, ttl: int = 3600) -> None:
        self._fallback.set_stage(session_id, stage, ttl)
        if self._redis_available and self._client:
            try:
                self._client.setex(f"caa:session:{session_id}:stage", ttl, stage)
            except Exception as e:
                logger.warning(f"Redis set_stage error: {e}")

    def get_stage(self, session_id: str) -> str:
        if self._redis_available and self._client:
            try:
                st = self._client.get(f"caa:session:{session_id}:stage")
                if st:
                    return str(st)
            except Exception as e:
                logger.warning(f"Redis get_stage error: {e}")
        return self._fallback.get_stage(session_id)


def get_session_store(redis_url: Optional[str] = None) -> ISessionStore:
    """Factory creating RedisSessionStore if redis_url is set and reachable, else InMemorySessionStore."""
    target_url = redis_url if redis_url is not None else os.getenv("REDIS_URL", "")
    if target_url:
        try:
            store = RedisSessionStore(redis_url=target_url)
            if store._redis_available:
                return store
        except Exception:
            pass
    return InMemorySessionStore()

