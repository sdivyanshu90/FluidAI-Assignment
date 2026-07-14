from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.guardrails import RequestGuard

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class AgentRequest(StrictModel):
    request: str = Field(
        min_length=10,
        max_length=5_000,
        description="Natural-language request for a structured business document.",
        examples=["Create a launch plan for a mobile banking application."],
    )

    @field_validator("request")
    @classmethod
    def apply_request_guardrails(cls, value: str) -> str:
        return RequestGuard.validate(value)

class ToolName(str, Enum):
    ANALYZE_REQUEST = "analyze_request"
    RECORD_ASSUMPTIONS = "record_assumptions"
    DRAFT_DOCUMENT = "draft_document"
    RENDER_DOCUMENT = "render_document"

class PlannedTask(StrictModel):
    id: str = Field(pattern=r"^task_[a-z0-9_]+$")
    title: str = Field(min_length=3, max_length=100)
    tool: ToolName
    description: str = Field(min_length=3, max_length=300)
    depends_on: list[str] = Field(default_factory=list, max_length=5)

class DocumentBrief(StrictModel):
    title: str = Field(min_length=3, max_length=160)
    document_type: str = Field(min_length=3, max_length=80)
    audience: str = Field(min_length=2, max_length=160)
    purpose: str = Field(min_length=3, max_length=500)
    goals: list[str] = Field(min_length=1, max_length=10)
    constraints: list[str] = Field(default_factory=list, max_length=10)
    assumptions: list[str] = Field(default_factory=list, max_length=10)

class AgentPlan(StrictModel):
    brief: DocumentBrief
    tasks: list[PlannedTask] = Field(min_length=3, max_length=5)

    @model_validator(mode="after")
    def validate_safe_task_graph(self) -> "AgentPlan":
        ids = [task.id for task in self.tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("task ids must be unique")

        known: set[str] = set()
        for task in self.tasks:
            missing = set(task.depends_on) - known
            if missing:
                raise ValueError(
                    f"task {task.id} has unknown or forward dependencies: {missing}"
                )
            known.add(task.id)

        tools = [task.tool for task in self.tasks]
        required_order = [
            ToolName.ANALYZE_REQUEST,
            ToolName.DRAFT_DOCUMENT,
            ToolName.RENDER_DOCUMENT,
        ]
        if any(tools.count(tool) != 1 for tool in required_order):
            raise ValueError("each required tool must occur exactly once")
        positions = [tools.index(tool) for tool in required_order]
        if positions != sorted(positions):
            raise ValueError("required tools are not in a safe semantic order")
        if tools.count(ToolName.RECORD_ASSUMPTIONS) > 1:
            raise ValueError("record_assumptions may occur at most once")
        if ToolName.RECORD_ASSUMPTIONS in tools and not (
            tools.index(ToolName.ANALYZE_REQUEST)
            < tools.index(ToolName.RECORD_ASSUMPTIONS)
            < tools.index(ToolName.DRAFT_DOCUMENT)
        ):
            raise ValueError("assumptions must be recorded between analysis and drafting")
        return self

class TableData(StrictModel):
    title: str | None = Field(default=None, max_length=120)
    headers: list[str] = Field(min_length=1, max_length=8)
    rows: list[list[str]] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def normalize_row_width(self) -> "TableData":
        width = len(self.headers)
        self.rows = [
            (row[:width] + [""] * width)[:width]
            for row in self.rows
        ]
        return self

class DocumentSection(StrictModel):
    heading: str = Field(min_length=2, max_length=120)
    paragraphs: list[str] = Field(default_factory=list, max_length=8)
    bullets: list[str] = Field(default_factory=list, max_length=15)
    table: TableData | None = None

class DocumentDraft(StrictModel):
    title: str = Field(min_length=3, max_length=160)
    subtitle: str | None = Field(default=None, max_length=200)
    audience: str = Field(min_length=2, max_length=160)
    executive_summary: str = Field(min_length=20, max_length=2_000)
    sections: list[DocumentSection] = Field(min_length=3, max_length=15)
    assumptions: list[str] = Field(default_factory=list, max_length=12)

TaskStatus = Literal["running", "completed", "failed"]

class TaskExecution(StrictModel):
    id: str
    title: str
    tool: ToolName
    status: TaskStatus
    output_summary: str | None = None
    duration_ms: int | None = None

class AgentResponse(StrictModel):
    job_id: str
    message: str
    document_name: str
    download_url: str
    provider: str
    document_type: str
    plan: list[TaskExecution]
    assumptions: list[str]
    guardrails_applied: list[str]
    duration_ms: int

class HealthResponse(StrictModel):
    status: Literal["ok"] = "ok"
    provider: Literal["gemini"] = "gemini"
    model: str
    api_key_configured: bool

JsonDict = dict[str, Any]
