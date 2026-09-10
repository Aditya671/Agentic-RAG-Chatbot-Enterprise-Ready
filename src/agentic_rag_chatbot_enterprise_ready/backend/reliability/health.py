"""Provider-neutral health and readiness contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable


class HealthStatus(str, Enum):
    """Deterministic service health states."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True, slots=True)
class HealthCheck:
    """One bounded operational check result."""

    name: str
    status: HealthStatus
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("health check name must be non-empty")
        if len(self.detail) > 500:
            raise ValueError("health check detail must be at most 500 characters")


@dataclass(frozen=True, slots=True)
class HealthReport:
    """Aggregated liveness/readiness result."""

    status: HealthStatus
    checks: tuple[HealthCheck, ...] = ()
    service: str = "agentic-rag"
    version: str = "unknown"
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.service.strip():
            raise ValueError("service must be non-empty")
        if not self.version.strip():
            raise ValueError("version must be non-empty")

    @property
    def ready(self) -> bool:
        return self.status == HealthStatus.HEALTHY

    def to_dict(self) -> dict[str, object]:
        return {
            "service": self.service,
            "version": self.version,
            "status": self.status.value,
            "ready": self.ready,
            "checks": [
                {
                    "name": check.name,
                    "status": check.status.value,
                    "detail": check.detail,
                }
                for check in self.checks
            ],
            "metadata": dict(self.metadata),
        }


CheckCallable = Callable[[], HealthCheck]


class HealthService:
    """Evaluate registered health checks without owning provider connections."""

    def __init__(
        self,
        checks: Iterable[CheckCallable] = (),
        *,
        service: str = "agentic-rag",
        version: str = "unknown",
    ) -> None:
        self._checks = tuple(checks)
        self.service = service
        self.version = version

    def liveness(self) -> HealthReport:
        """Return process-level liveness without external dependency checks."""
        return HealthReport(
            status=HealthStatus.HEALTHY,
            service=self.service,
            version=self.version,
            metadata={"probe": "liveness"},
        )

    def readiness(self) -> HealthReport:
        """Evaluate configured dependency checks and aggregate conservatively."""
        results: list[HealthCheck] = []
        for check in self._checks:
            try:
                result = check()
            except Exception as exc:
                results.append(
                    HealthCheck(
                        name=getattr(check, "__name__", "dependency"),
                        status=HealthStatus.UNHEALTHY,
                        detail=f"check failed: {type(exc).__name__}",
                    )
                )
                continue
            if not isinstance(result, HealthCheck):
                raise TypeError("health checks must return HealthCheck")
            results.append(result)

        if not results:
            status = HealthStatus.HEALTHY
        elif any(item.status == HealthStatus.UNHEALTHY for item in results):
            status = HealthStatus.UNHEALTHY
        elif any(item.status == HealthStatus.DEGRADED for item in results):
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY

        return HealthReport(
            status=status,
            checks=tuple(results),
            service=self.service,
            version=self.version,
            metadata={"probe": "readiness"},
        )
