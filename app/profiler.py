"""
Request profiling and timing utilities for performance analysis
"""

import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import structlog

logger = structlog.get_logger()


@dataclass
class TimingEntry:
    """Individual timing measurement"""

    name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def finish(self, **metadata: Any) -> float:
        """Mark timing as finished and calculate duration"""
        self.end_time = time.perf_counter()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.metadata.update(metadata)
        return self.duration_ms


class RequestProfiler:
    """Tracks timing for different phases of request processing"""

    def __init__(self, request_id: str) -> None:
        self.request_id = request_id
        self.timings: List[TimingEntry] = []
        self.start_time = time.perf_counter()
        self.real_start_time = datetime.now()  # Real wall-clock timestamp
        self.nested_stack: List[str] = []  # Track nested timings
        self.session_metadata: Dict[str, Any] = {}  # Store session-level metadata

    def start_timing(self, name: str, **metadata: Any) -> TimingEntry:
        """Start timing a named phase"""
        entry = TimingEntry(
            name=name, start_time=time.perf_counter(), metadata=metadata
        )
        self.timings.append(entry)
        return entry

    def set_metadata(self, key: str, value: Any) -> None:
        """Set session-level metadata (e.g., model information)"""
        self.session_metadata[key] = value

    @asynccontextmanager
    async def time_phase(
        self, name: str, **metadata: Any
    ) -> AsyncGenerator[TimingEntry, None]:
        """Context manager for timing a phase"""
        entry = self.start_timing(name, **metadata)
        self.nested_stack.append(name)
        try:
            yield entry
        finally:
            duration = entry.finish()
            self.nested_stack.pop()

            # Log at debug level without indentation for clean alignment
            logger.debug(
                f"profiler: {name}",
                request_id=self.request_id,
                duration_ms=duration,
                **metadata,
            )

    def get_total_time(self) -> float:
        """Get total time since profiler creation"""
        return round((time.perf_counter() - self.start_time) * 1000, 2)

    def get_summary(self) -> Dict[str, Any]:
        """Get timing summary for this request"""
        finished_timings = [t for t in self.timings if t.duration_ms is not None]

        # Use sum of completed phases as total time to avoid continuously growing values
        total_phase_time = (
            sum(t.duration_ms for t in finished_timings if t.duration_ms is not None)
            if finished_timings
            else 0
        )

        return {
            "request_id": self.request_id,
            "total_time_ms": total_phase_time,
            "phase_count": len(finished_timings),
            "real_start_time": self.real_start_time.isoformat(),  # Real timestamp
            "metadata": self.session_metadata,  # Include session metadata
            "phases": [
                {"name": t.name, "duration_ms": t.duration_ms, "metadata": t.metadata}
                for t in finished_timings
            ],
            "breakdown": {t.name: t.duration_ms for t in finished_timings},
        }

    def get_slowest_phases(self, limit: int = 5) -> List[TimingEntry]:
        """Get the slowest phases"""
        finished_timings = [t for t in self.timings if t.duration_ms is not None]
        return sorted(finished_timings, key=lambda x: x.duration_ms or 0, reverse=True)[
            :limit
        ]


# Global storage for request profilers
_active_profilers: Dict[str, RequestProfiler] = {}


def get_profiler(request_id: str) -> Optional[RequestProfiler]:
    """Get profiler for a request"""
    return _active_profilers.get(request_id)


def create_profiler(request_id: str) -> RequestProfiler:
    """Create and register a new profiler"""
    profiler = RequestProfiler(request_id)
    _active_profilers[request_id] = profiler
    return profiler


def cleanup_profiler(request_id: str) -> Optional[Dict[str, Any]]:
    """Remove profiler and return summary"""
    profiler = _active_profilers.pop(request_id, None)
    if profiler:
        return profiler.get_summary()
    return None


def cleanup_old_profilers(max_age_seconds: int = 300) -> None:
    """Clean up profilers older than max_age_seconds"""
    current_time = time.perf_counter()
    to_remove = []

    for request_id, profiler in _active_profilers.items():
        age = current_time - profiler.start_time
        if age > max_age_seconds:
            to_remove.append(request_id)

    for request_id in to_remove:
        _active_profilers.pop(request_id, None)

    if to_remove:
        logger.debug(f"Cleaned up {len(to_remove)} old profilers")


# Convenience functions for common timing patterns


async def time_json_operation(
    profiler: RequestProfiler, operation: str, data_size: Optional[int] = None
) -> AsyncGenerator[TimingEntry, None]:
    """Time JSON parsing/serialization operations"""
    metadata: Dict[str, Any] = {"operation": operation}
    if data_size:
        metadata["data_size_bytes"] = data_size
    async with profiler.time_phase(f"json_{operation}", **metadata) as entry:
        yield entry


async def time_network_request(
    profiler: RequestProfiler, method: str, url: str
) -> AsyncGenerator[TimingEntry, None]:
    """Time network requests"""
    async with profiler.time_phase("network_request", method=method, url=url) as entry:
        yield entry


async def time_mcp_operation(
    profiler: RequestProfiler,
    operation: str,
    server: Optional[str] = None,
    tool: Optional[str] = None,
) -> AsyncGenerator[TimingEntry, None]:
    """Time MCP operations"""
    metadata: Dict[str, Any] = {"operation": operation}
    if server:
        metadata["server"] = server
    if tool:
        metadata["tool"] = tool
    async with profiler.time_phase(f"mcp_{operation}", **metadata) as entry:
        yield entry


async def time_plugin_execution(
    profiler: RequestProfiler, plugin_type: str, plugin_count: Optional[int] = None
) -> AsyncGenerator[TimingEntry, None]:
    """Time plugin execution"""
    metadata: Dict[str, Any] = {"plugin_type": plugin_type}
    if plugin_count:
        metadata["plugin_count"] = plugin_count
    async with profiler.time_phase(f"plugin_{plugin_type}", **metadata) as entry:
        yield entry
