"""
Production-grade Circuit Breaker Pattern implementation.
Protects external dependencies (GitHub MCP, Jira Cloud REST API, Bedrock LLM)
from cascading failures, hanging timeouts, and repeated network degradation.

States:
- CLOSED: Normal execution. Failures increment failure counter.
- OPEN: Tripped. Calls immediately fail-fast and invoke fallback without waiting.
- HALF_OPEN: Probe state after recovery_timeout. Success resets to CLOSED; failure trips back to OPEN.
"""
import time
import logging
import threading
import functools
from enum import Enum
from typing import Callable, Any, Optional, Tuple, Type

logger = logging.getLogger("circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenException(Exception):
    """Raised when an operation is attempted while the circuit breaker is OPEN and no fallback is supplied."""
    def __init__(self, breaker_name: str, message: str = ""):
        self.breaker_name = breaker_name
        super().__init__(message or f"Circuit breaker '{breaker_name}' is OPEN. Fast-failing external call.")


class CircuitBreaker:
    """
    Thread-safe Circuit Breaker supporting both sync and async execution with fallbacks.
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        half_open_success_threshold: int = 1,
        expected_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_success_threshold = half_open_success_threshold
        self.expected_exceptions = expected_exceptions

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._last_state_change: float = time.time()
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN and self._last_failure_time is not None:
                if (time.time() - self._last_failure_time) >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    self._last_state_change = time.time()
                    logger.info(f"[CircuitBreaker:{self.name}] Transitioned from OPEN to HALF_OPEN (probing recovery).")
            return self._state

    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitState.HALF_OPEN

    def record_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    self._last_state_change = time.time()
                    logger.info(f"[CircuitBreaker:{self.name}] Recovered! Transitioned from HALF_OPEN to CLOSED.")
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def record_failure(self, exception: Exception) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._state in (CircuitState.CLOSED, CircuitState.HALF_OPEN):
                if self._failure_count >= self.failure_threshold or self._state == CircuitState.HALF_OPEN:
                    self._state = CircuitState.OPEN
                    self._last_state_change = time.time()
                    logger.warning(
                        f"[CircuitBreaker:{self.name}] Tripped to OPEN! Failure count: {self._failure_count} "
                        f"(Last error: {exception}). Fast-failing for {self.recovery_timeout}s."
                    )

    def reset(self) -> None:
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._last_state_change = time.time()
            logger.info(f"[CircuitBreaker:{self.name}] Manually reset to CLOSED.")

    def call(self, func: Callable, *args, fallback: Optional[Callable] = None, **kwargs) -> Any:
        """Executes a synchronous callable through the circuit breaker."""
        current_state = self.state

        if current_state == CircuitState.OPEN:
            logger.debug(f"[CircuitBreaker:{self.name}] Fast-failing call in OPEN state.")
            if fallback is not None:
                return fallback(*args, **kwargs)
            raise CircuitBreakerOpenException(self.name)

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except self.expected_exceptions as e:
            self.record_failure(e)
            if fallback is not None:
                logger.info(f"[CircuitBreaker:{self.name}] Invoking fallback following error: {e}")
                return fallback(*args, **kwargs)
            raise

    async def call_async(self, coro_func: Callable, *args, fallback: Optional[Callable] = None, **kwargs) -> Any:
        """Executes an asynchronous coroutine through the circuit breaker."""
        import inspect

        current_state = self.state
        if current_state == CircuitState.OPEN:
            logger.debug(f"[CircuitBreaker:{self.name}] Fast-failing async call in OPEN state.")
            if fallback is not None:
                if inspect.iscoroutinefunction(fallback):
                    return await fallback(*args, **kwargs)
                return fallback(*args, **kwargs)
            raise CircuitBreakerOpenException(self.name)

        try:
            result = await coro_func(*args, **kwargs)
            self.record_success()
            return result
        except self.expected_exceptions as e:
            self.record_failure(e)
            if fallback is not None:
                logger.info(f"[CircuitBreaker:{self.name}] Invoking async fallback following error: {e}")
                if inspect.iscoroutinefunction(fallback):
                    return await fallback(*args, **kwargs)
                return fallback(*args, **kwargs)
            raise

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self._last_failure_time
        }

