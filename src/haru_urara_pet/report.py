"""Stable human- and machine-readable reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True, slots=True)
class Issue:
    severity: Severity
    code: str
    message: str
    location: str | None = None
    repair: str | None = None


@dataclass(slots=True)
class Report:
    subject: str
    issues: list[Issue] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def add(
        self,
        severity: Severity,
        code: str,
        message: str,
        location: str | Path | None = None,
        repair: str | None = None,
    ) -> None:
        self.issues.append(
            Issue(
                severity=severity,
                code=code,
                message=message,
                location=str(location) if location is not None else None,
                repair=repair,
            )
        )

    def merge(self, other: Report, prefix: str | None = None) -> None:
        for issue in other.issues:
            code = f"{prefix}.{issue.code}" if prefix else issue.code
            self.issues.append(
                Issue(
                    severity=issue.severity,
                    code=code,
                    message=issue.message,
                    location=issue.location,
                    repair=issue.repair,
                )
            )
        self.facts.update(other.facts)

    def to_dict(self) -> dict[str, Any]:
        counts = {
            severity: sum(issue.severity == severity for issue in self.issues)
            for severity in ("error", "warning", "info")
        }
        return {
            "ok": self.ok,
            "subject": self.subject,
            "counts": counts,
            "facts": self.facts,
            "issues": [asdict(issue) for issue in self.issues],
        }
