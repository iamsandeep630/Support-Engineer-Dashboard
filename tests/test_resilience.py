"""
Unit tests for Resilience & Fault Tolerance components:
1. CircuitBreaker (CLOSED -> OPEN -> HALF_OPEN -> CLOSED state lifecycle, fallbacks, exception handling)
2. ISessionStore (InMemorySessionStore & RedisSessionStore fallback, TTL, pending actions, history)
"""
import unittest
import time
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add backend to path
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from resilience.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerOpenException
from resilience.session_store import InMemorySessionStore, RedisSessionStore, get_session_store


class TestCircuitBreaker(unittest.TestCase):

    def test_normal_successful_calls_keep_closed(self):
        cb = CircuitBreaker(name="test_service", failure_threshold=3, recovery_timeout=0.2)
        res = cb.call(lambda x: x * 2, 5)
        self.assertEqual(res, 10)
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertTrue(cb.is_closed)

    def test_trips_to_open_after_threshold_failures(self):
        cb = CircuitBreaker(name="test_service", failure_threshold=2, recovery_timeout=0.2)

        def failing():
            raise ConnectionError("Service unreachable")

        # First failure
        with self.assertRaises(ConnectionError):
            cb.call(failing)
        self.assertEqual(cb.state, CircuitState.CLOSED)

        # Second failure -> trips to OPEN
        with self.assertRaises(ConnectionError):
            cb.call(failing)
        self.assertEqual(cb.state, CircuitState.OPEN)
        self.assertTrue(cb.is_open)

    def test_open_circuit_invokes_fallback_immediately(self):
        cb = CircuitBreaker(name="test_service", failure_threshold=1, recovery_timeout=0.2)

        def failing():
            raise TimeoutError("Timeout")

        # Trip to OPEN
        with self.assertRaises(TimeoutError):
            cb.call(failing)
        self.assertTrue(cb.is_open)

        # Subsequent call invokes fallback fast without raising or executing function
        called_original = []
        fallback_res = cb.call(
            lambda: called_original.append(1),
            fallback=lambda: "fallback_payload"
        )
        self.assertEqual(fallback_res, "fallback_payload")
        self.assertEqual(len(called_original), 0)

    def test_half_open_recovery_transition(self):
        cb = CircuitBreaker(name="test_service", failure_threshold=1, recovery_timeout=0.1)

        # Trip to OPEN
        with self.assertRaises(ValueError):
            cb.call(lambda: int("invalid"))
        self.assertTrue(cb.is_open)

        # Wait for recovery timeout
        time.sleep(0.12)
        self.assertTrue(cb.is_half_open)

        # Successful probe call recovers circuit to CLOSED
        res = cb.call(lambda: 42)
        self.assertEqual(res, 42)
        self.assertTrue(cb.is_closed)


class TestSessionStore(unittest.TestCase):

    def test_in_memory_session_store_lifecycle(self):
        store = InMemorySessionStore()
        session_id = "test-session-1"

        # Staging action
        action = {"action_id": "act-1", "target_file": "backend/test.py", "defect_type": "SYNTAX"}
        store.save_pending_action(session_id, action, ttl=60)

        retrieved = store.get_pending_action(session_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["action_id"], "act-1")
        self.assertEqual(store.get_stage(session_id), "STAGE_1_INVESTIGATION")

        # History turns
        store.append_history(session_id, "user", "Check bug in test.py")
        store.append_history(session_id, "assistant", "Proposed fix staged")
        history = store.get_history(session_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")

        # Clear action
        store.clear_pending_action(session_id)
        self.assertIsNone(store.get_pending_action(session_id))

    def test_session_store_factory_fallback(self):
        # Factory with empty url returns InMemorySessionStore
        store = get_session_store(redis_url="")
        self.assertIsInstance(store, InMemorySessionStore)

        # Factory with unreachable redis url safely returns InMemorySessionStore
        store_unreachable = get_session_store(redis_url="redis://nonexistent-host:6379/0")
        self.assertIsInstance(store_unreachable, InMemorySessionStore)


if __name__ == "__main__":
    unittest.main()

