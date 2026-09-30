"""Agent interfaces (Backend Plan §11).

AI integration stays behind these boundaries; the AI Developer Plan replaces
the stub implementations without touching orchestration.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RequirementTurn:
    assistant_message: str
    requirements: dict[str, Any]
    completion: int
    missing_fields: list[str]
    ready: bool


@dataclass
class ReviewIssue:
    id: str
    severity: str
    file: str
    problem: str
    recommendation: str


@dataclass
class ReviewResult:
    status: str  # PASS | FAIL
    issues: list[ReviewIssue] = field(default_factory=list)


@dataclass
class TestResult:
    status: str  # PASSED | FAILED
    category: str | None
    files: list[str]
    summary: str
    suggested_fix: str | None = None
    # Normalized per-step records from the build/test runner (Backend Plan §10).
    commands: list[dict[str, Any]] = field(default_factory=list)


class RequirementAgent(ABC):
    @abstractmethod
    async def run(
        self, requirements: dict[str, Any], chat: list[dict[str, Any]], message: str
    ) -> RequirementTurn: ...

    @abstractmethod
    async def autofill(
        self, requirements: dict[str, Any], chat: list[dict[str, Any]]
    ) -> RequirementTurn:
        """Fill remaining missing fields with best-practice suggestions."""


class ArchitectAgent(ABC):
    @abstractmethod
    async def run(self, requirements: dict[str, Any]) -> dict[str, Any]: ...


class DeveloperAgent(ABC):
    @abstractmethod
    async def run(
        self,
        project_id: str,
        requirements: dict[str, Any],
        architecture: dict[str, Any],
        feedback: list[str] | None = None,
    ) -> list[str]:
        """Write files into the project workspace, return relative paths written."""


class ReviewerAgent(ABC):
    @abstractmethod
    async def run(
        self, requirements: dict[str, Any], architecture: dict[str, Any], files: list[str]
    ) -> ReviewResult: ...


class TesterAgent(ABC):
    @abstractmethod
    async def run(self, project_id: str) -> TestResult: ...
