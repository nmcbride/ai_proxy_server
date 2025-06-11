"""
Profiling endpoint for performance analysis
"""

import json
import time
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import structlog

from app.profiler import _active_profilers, cleanup_old_profilers

logger = structlog.get_logger()

# Router for profiling endpoints
profiling_router = APIRouter(prefix="/profiling", tags=["profiling"])


class ProfilingResponse(BaseModel):
    """Response model for profiling data"""
    request_id: str
    total_time_ms: float
    phase_count: int
    phases: list
    breakdown: Dict[str, float]
    slowest_phases: list


class ProfilingStatsResponse(BaseModel):
    """Response model for profiling statistics"""
    active_profiles: int
    total_requests: int
    avg_request_time_ms: Optional[float]
    slowest_requests: list


@profiling_router.get("/request/{request_id}", response_model=ProfilingResponse)
async def get_request_profile(request_id: str):
    """Get profiling data for a specific request"""
    profiler = _active_profilers.get(request_id)
    
    if not profiler:
        raise HTTPException(
            status_code=404,
            detail=f"Profiling data not found for request {request_id}"
        )
    
    summary = profiler.get_summary()
    slowest_phases = profiler.get_slowest_phases()
    
    return ProfilingResponse(
        request_id=summary["request_id"],
        total_time_ms=summary["total_time_ms"],
        phase_count=summary["phase_count"],
        phases=summary["phases"],
        breakdown=summary["breakdown"],
        slowest_phases=[
            {
                "name": phase.name,
                "duration_ms": phase.duration_ms,
                "metadata": phase.metadata
            }
            for phase in slowest_phases
        ]
    )


@profiling_router.get("/active", response_model=ProfilingStatsResponse)
async def get_active_profiles(
    limit: int = Query(10, description="Number of requests to include in slowest_requests")
):
    """Get statistics about active profiling sessions"""
    cleanup_old_profilers(max_age_seconds=3600)  # Keep profiles for 1 hour for dashboard viewing
    
    if not _active_profilers:
        return ProfilingStatsResponse(
            active_profiles=0,
            total_requests=0,
            avg_request_time_ms=None,
            slowest_requests=[]
        )
    
    # Calculate statistics
    total_requests = len(_active_profilers)
    # For completed requests, use sum of phase durations; for active ones, use total elapsed time
    total_times = []
    for profiler in _active_profilers.values():
        summary = profiler.get_summary()
        if summary["phases"]:
            # If there are completed phases, use the sum of their durations
            phase_time = sum(phase["duration_ms"] for phase in summary["phases"])
            total_times.append(phase_time)
        else:
            # If no phases completed yet, this is likely an active request, skip it for average calculation
            # since we can't get a meaningful completion time
            pass
    avg_time = sum(total_times) / len(total_times) if total_times else None
    
    # Get slowest requests (sort by sum of phase durations)
    profiler_items = list(_active_profilers.items())
    def get_request_duration(profiler):
        summary = profiler.get_summary()
        return summary["total_time_ms"]
    profiler_items.sort(key=lambda x: get_request_duration(x[1]), reverse=True)
    
    slowest_requests = []
    for request_id, profiler in profiler_items[:limit]:
        summary = profiler.get_summary()
        slowest_requests.append({
            "request_id": request_id,
            "total_time_ms": summary["total_time_ms"],
            "phase_count": summary["phase_count"],
            "slowest_phase": summary["phases"][0]["name"] if summary["phases"] else None
        })
    
    return ProfilingStatsResponse(
        active_profiles=total_requests,
        total_requests=total_requests,
        avg_request_time_ms=avg_time,
        slowest_requests=slowest_requests
    )


@profiling_router.get("/export/{request_id}")
async def export_request_profile(request_id: str):
    """Export detailed profiling data as JSON for external analysis"""
    profiler = _active_profilers.get(request_id)
    
    if not profiler:
        raise HTTPException(
            status_code=404,
            detail=f"Profiling data not found for request {request_id}"
        )
    
    # Get full profiling data including timing entries
    # Calculate how long ago this request started (in milliseconds)
    current_time = time.perf_counter()
    request_age_ms = (current_time - profiler.start_time) * 1000
    
    detailed_data = {
        "request_id": request_id,
        "summary": profiler.get_summary(),
        "raw_timings": [
            {
                "name": timing.name,
                "start_time": timing.start_time,
                "end_time": timing.end_time,
                "duration_ms": timing.duration_ms,
                "metadata": timing.metadata
            }
            for timing in profiler.timings
        ],
        "nested_stack_depth": len(profiler.nested_stack),
        "export_timestamp": request_age_ms
    }
    
    return detailed_data


@profiling_router.delete("/cleanup")
async def cleanup_profiles(max_age_seconds: int = Query(300, description="Maximum age in seconds")):
    """Clean up old profiling data"""
    initial_count = len(_active_profilers)
    cleanup_old_profilers(max_age_seconds)
    final_count = len(_active_profilers)
    
    cleaned_count = initial_count - final_count
    
    logger.info(
        "Manual profiler cleanup completed",
        initial_count=initial_count,
        final_count=final_count,
        cleaned_count=cleaned_count,
        max_age_seconds=max_age_seconds
    )
    
    return {
        "message": f"Cleaned up {cleaned_count} old profiles",
        "initial_count": initial_count,
        "final_count": final_count,
        "max_age_seconds": max_age_seconds
    }


@profiling_router.get("/health")
async def profiling_health():
    """Health check for profiling system"""
    return {
        "status": "healthy",
        "active_profiles": len(_active_profilers),
        "profiling_enabled": True
    } 