"""
Metrics and monitoring for Cray workflows.

Features:
- Prometheus-compatible metrics export
- Workflow execution metrics (duration, success rate)
- Step-level metrics
- Resource usage tracking
- Real-time monitoring dashboard data
"""

import time
import asyncio
import threading
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
from contextlib import contextmanager
from loguru import logger

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


@dataclass
class MetricPoint:
    """A single metric data point."""
    name: str
    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class WorkflowMetrics:
    """Metrics for a single workflow execution."""
    workflow_name: str
    run_id: str
    start_time: float
    end_time: Optional[float] = None
    status: str = "running"
    steps_total: int = 0
    steps_completed: int = 0
    steps_failed: int = 0
    step_durations: Dict[str, float] = field(default_factory=dict)
    error: Optional[str] = None
    
    @property
    def duration(self) -> float:
        """Total workflow duration in seconds."""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    @property
    def success_rate(self) -> float:
        """Step success rate (0-1)."""
        if self.steps_total == 0:
            return 0.0
        return self.steps_completed / self.steps_total


class MetricsCollector:
    """
    Collects and aggregates workflow metrics.
    
    Usage:
        collector = MetricsCollector()
        
        # Track workflow execution
        with collector.track_workflow("my-workflow", "run-123") as wf:
            with wf.track_step("step-1"):
                # execute step
                pass
        
        # Get metrics
        metrics = collector.get_prometheus_metrics()
    """
    
    def __init__(self, retention_hours: int = 24):
        """
        Initialize metrics collector.
        
        Args:
            retention_hours: How long to keep historical metrics
        """
        self.retention_hours = retention_hours
        self._workflows: Dict[str, WorkflowMetrics] = {}
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        _histograms: Dict[str, List[float]] = defaultdict(list)
        self._histograms = _histograms
        self._lock = threading.Lock()
        self._start_time = time.time()
        
        # Start cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
    
    def start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        async def cleanup_loop():
            while True:
                await asyncio.sleep(3600)  # Run every hour
                self._cleanup_old_metrics()
        
        try:
            loop = asyncio.get_event_loop()
            self._cleanup_task = loop.create_task(cleanup_loop())
        except RuntimeError:
            pass
    
    def _cleanup_old_metrics(self) -> None:
        """Remove metrics older than retention period."""
        cutoff = time.time() - (self.retention_hours * 3600)
        
        with self._lock:
            to_remove = [
                run_id for run_id, wf in self._workflows.items()
                if wf.end_time and wf.end_time < cutoff
            ]
            for run_id in to_remove:
                del self._workflows[run_id]
        
        if to_remove:
            logger.debug(f"Cleaned up {len(to_remove)} old metric records")
    
    @contextmanager
    def track_workflow(self, workflow_name: str, run_id: str):
        """
        Context manager to track workflow execution.
        
        Args:
            workflow_name: Name of the workflow
            run_id: Unique run identifier
        """
        metrics = WorkflowMetrics(
            workflow_name=workflow_name,
            run_id=run_id,
            start_time=time.time()
        )
        
        with self._lock:
            self._workflows[run_id] = metrics
        
        try:
            yield metrics
            metrics.status = "success"
        except Exception as e:
            metrics.status = "failed"
            metrics.error = str(e)
            raise
        finally:
            metrics.end_time = time.time()
            
            # Update counters
            self._increment_counter(
                f"cray_workflow_total",
                labels={"workflow": workflow_name, "status": metrics.status}
            )
            self._record_histogram(
                f"cray_workflow_duration_seconds",
                metrics.duration,
                labels={"workflow": workflow_name}
            )
    
    def _increment_counter(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment a counter metric."""
        key = self._make_key(name, labels)
        with self._lock:
            self._counters[key] += value
    
    def _set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Set a gauge metric."""
        key = self._make_key(name, labels)
        with self._lock:
            self._gauges[key] = value
    
    def _record_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a histogram value."""
        key = self._make_key(name, labels)
        with self._lock:
            self._histograms[key].append(value)
            # Keep last 1000 values
            if len(self._histograms[key]) > 1000:
                self._histograms[key] = self._histograms[key][-1000:]
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Create a unique key for a metric."""
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def record_step(
        self,
        run_id: str,
        step_name: str,
        duration: float,
        success: bool,
        plugin: str = ""
    ) -> None:
        """
        Record step execution metrics.
        
        Args:
            run_id: Workflow run ID
            step_name: Name of the step
            duration: Step duration in seconds
            success: Whether step succeeded
            plugin: Plugin used
        """
        with self._lock:
            if run_id in self._workflows:
                wf = self._workflows[run_id]
                wf.steps_total += 1
                if success:
                    wf.steps_completed += 1
                else:
                    wf.steps_failed += 1
                wf.step_durations[step_name] = duration
        
        # Record metrics
        status = "success" if success else "failed"
        self._increment_counter(
            "cray_step_total",
            labels={"step": step_name, "status": status, "plugin": plugin}
        )
        self._record_histogram(
            "cray_step_duration_seconds",
            duration,
            labels={"step": step_name, "plugin": plugin}
        )
    
    def get_workflow_metrics(self, workflow_name: Optional[str] = None) -> List[WorkflowMetrics]:
        """
        Get workflow execution metrics.
        
        Args:
            workflow_name: Filter by workflow name (optional)
            
        Returns:
            List of workflow metrics
        """
        with self._lock:
            metrics = list(self._workflows.values())
        
        if workflow_name:
            metrics = [m for m in metrics if m.workflow_name == workflow_name]
        
        return sorted(metrics, key=lambda m: m.start_time, reverse=True)
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get metrics summary.
        
        Returns:
            Summary statistics
        """
        with self._lock:
            workflows = list(self._workflows.values())
            counters = dict(self._counters)
        
        # Count from counters
        total_runs = 0
        successful = 0
        failed = 0
        running = 0
        for key, value in counters.items():
            if "cray_workflow_total" in key:
                total_runs += value
                if 'status="success"' in key:
                    successful += value
                elif 'status="failed"' in key:
                    failed += value
                elif 'status="running"' in key:
                    running += value
        
        # Fallback to workflow dict if no counters
        if total_runs == 0:
            total_runs = len(workflows)
            successful = sum(1 for w in workflows if w.status == "success")
            failed = sum(1 for w in workflows if w.status == "failed")
            running = sum(1 for w in workflows if w.status == "running")
        
        durations = [w.duration for w in workflows if w.end_time]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            "total_runs": total_runs,
            "successful": successful,
            "failed": failed,
            "running": running,
            "success_rate": successful / total_runs if total_runs > 0 else 0,
            "avg_duration_seconds": avg_duration,
            "uptime_seconds": time.time() - self._start_time,
        }
    
    def get_prometheus_metrics(self) -> str:
        """
        Export metrics in Prometheus format.
        
        Returns:
            Prometheus-formatted metrics string
        """
        lines = []
        
        # Workflow metrics
        lines.append("# HELP cray_workflow_total Total workflow executions")
        lines.append("# TYPE cray_workflow_total counter")
        
        with self._lock:
            counters = dict(self._counters)
            gauges = dict(self._gauges)
            histograms = {k: list(v) for k, v in self._histograms.items()}
        
        for key, value in counters.items():
            if "workflow_total" in key:
                lines.append(f"{key} {value}")
        
        lines.append("")
        lines.append("# HELP cray_workflow_duration_seconds Workflow execution duration")
        lines.append("# TYPE cray_workflow_duration_seconds histogram")
        
        for key, values in histograms.items():
            if "workflow_duration" in key and values:
                # Calculate histogram buckets
                sorted_values = sorted(values)
                count = len(sorted_values)
                sum_val = sum(sorted_values)
                
                lines.append(f"{key}_bucket{{le=\"+Inf\"}} {count}")
                lines.append(f"{key}_sum {sum_val}")
                lines.append(f"{key}_count {count}")
        
        lines.append("")
        lines.append("# HELP cray_step_total Total step executions")
        lines.append("# TYPE cray_step_total counter")
        
        for key, value in counters.items():
            if "step_total" in key:
                lines.append(f"{key} {value}")
        
        lines.append("")
        lines.append("# HELP cray_step_duration_seconds Step execution duration")
        lines.append("# TYPE cray_step_duration_seconds histogram")
        
        for key, values in histograms.items():
            if "step_duration" in key and values:
                sorted_values = sorted(values)
                count = len(sorted_values)
                sum_val = sum(sorted_values)
                
                lines.append(f"{key}_bucket{{le=\"+Inf\"}} {count}")
                lines.append(f"{key}_sum {sum_val}")
                lines.append(f"{key}_count {count}")
        
        # System metrics
        lines.append("")
        lines.append("# HELP cray_up Cray service status")
        lines.append("# TYPE cray_up gauge")
        lines.append("cray_up 1")
        
        lines.append("")
        lines.append("# HELP cray_uptime_seconds Service uptime")
        lines.append("# TYPE cray_uptime_seconds gauge")
        lines.append(f"cray_uptime_seconds {time.time() - self._start_time}")
        
        if PSUTIL_AVAILABLE:
            lines.append("")
            lines.append("# HELP cray_memory_usage_bytes Memory usage")
            lines.append("# TYPE cray_memory_usage_bytes gauge")
            process = psutil.Process()
            lines.append(f"cray_memory_usage_bytes {process.memory_info().rss}")
            
            lines.append("")
            lines.append("# HELP cray_cpu_usage_percent CPU usage")
            lines.append("# TYPE cray_cpu_usage_percent gauge")
            lines.append(f"cray_cpu_usage_percent {process.cpu_percent()}")
        
        return "\n".join(lines)


class MetricsMiddleware:
    """
    Middleware to automatically track metrics for workflow runs.
    """
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
    
    async def before_run(self, workflow: Any, task: Any) -> None:
        """Called before workflow execution."""
        # Metrics are tracked via context manager in runner
        pass
    
    async def after_run(self, workflow: Any, task: Any) -> None:
        """Called after workflow execution."""
        # Metrics are finalized in context manager
        pass
    
    async def on_step_start(self, step: Any, task: Any) -> float:
        """Called when a step starts. Returns start time."""
        return time.time()
    
    async def on_step_end(
        self,
        step: Any,
        task: Any,
        start_time: float,
        success: bool,
        error: Optional[str] = None
    ) -> None:
        """Called when a step ends."""
        duration = time.time() - start_time
        self.collector.record_step(
            run_id=task.id,
            step_name=step.name,
            duration=duration,
            success=success,
            plugin=step.plugin
        )


# Global metrics collector
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
