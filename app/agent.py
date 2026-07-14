from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar
from uuid import uuid4
from pydantic import BaseModel, ValidationError
from app.config import Settings
from app.documents import render_docx, safe_document_name
from app.guardrails import APPLIED_GUARDRAILS
from app.llm.providers import LLMError, LLMProvider
from app.prompts import DRAFTING_PROMPT, PLANNING_PROMPT
from app.schemas import (
    AgentPlan,
    AgentResponse,
    DocumentDraft,
    PlannedTask,
    TaskExecution,
    ToolName,
)

class AgentExecutionError(RuntimeError):
    """Safe failure surfaced through the API without exposing credentials or prompts."""

ModelT = TypeVar("ModelT", bound=BaseModel)

@dataclass(slots=True)
class ExecutionState:
    request: str
    plan: AgentPlan
    draft: DocumentDraft | None = None
    destination: Path | None = None
    providers: list[str] = field(default_factory=list)
    executions: list[TaskExecution] = field(default_factory=list)

class DocumentAgent:
    """Plans and executes a guarded, bounded document-generation workflow."""

    def __init__(self, settings: Settings, provider: LLMProvider) -> None:
        self._settings = settings
        self._provider = provider

    async def run(self, request: str, base_url: str = "") -> AgentResponse:
        started = time.perf_counter()
        job_id = uuid4().hex
        try:
            plan, provider_name = await self._generate_model(
                model=AgentPlan,
                operation="plan",
                system_prompt=PLANNING_PROMPT,
                payload={"request": request},
            )
        except (LLMError, ValidationError, ValueError) as exc:
            raise AgentExecutionError(f"Planning failed: {exc}") from exc

        state = ExecutionState(request=request, plan=plan, providers=[provider_name])
        for task in plan.tasks:
            await self._execute_task(task, state, job_id)

        if state.destination is None:
            raise AgentExecutionError("The agent finished without producing a document.")
        provider_summary = ", ".join(dict.fromkeys(state.providers))
        return AgentResponse(
            job_id=job_id,
            message=(
                "Document generated successfully after guarded autonomous planning "
                "and tool execution."
            ),
            document_name=state.destination.name,
            download_url=f"{base_url}/documents/{state.destination.name}",
            provider=provider_summary,
            document_type=state.plan.brief.document_type,
            plan=state.executions,
            assumptions=state.plan.brief.assumptions,
            guardrails_applied=APPLIED_GUARDRAILS,
            duration_ms=int((time.perf_counter() - started) * 1_000),
        )

    async def _execute_task(
        self, task: PlannedTask, state: ExecutionState, job_id: str
    ) -> None:
        if not self._dependencies_satisfied(task, state):
            raise AgentExecutionError(f"Dependencies were not satisfied for {task.title}.")

        execution = TaskExecution(
            id=task.id, title=task.title, tool=task.tool, status="running"
        )
        state.executions.append(execution)
        started = time.perf_counter()
        try:
            execution.output_summary = await self._invoke_tool(task.tool, state, job_id)
            execution.status = "completed"
        except (AgentExecutionError, LLMError, ValidationError, OSError, ValueError) as exc:
            execution.status = "failed"
            execution.output_summary = str(exc)
            raise AgentExecutionError(f"Task '{task.title}' failed: {exc}") from exc
        finally:
            execution.duration_ms = int((time.perf_counter() - started) * 1_000)

    async def _invoke_tool(
        self, tool: ToolName, state: ExecutionState, job_id: str
    ) -> str:
        if tool == ToolName.ANALYZE_REQUEST:
            return (
                f"Identified a {state.plan.brief.document_type} for "
                f"{state.plan.brief.audience}."
            )
        if tool == ToolName.RECORD_ASSUMPTIONS:
            return f"Recorded {len(state.plan.brief.assumptions)} explicit assumptions."
        if tool == ToolName.DRAFT_DOCUMENT:
            state.draft, provider_name = await self._generate_model(
                model=DocumentDraft,
                operation="draft",
                system_prompt=DRAFTING_PROMPT,
                payload={
                    "request": state.request,
                    "brief": state.plan.brief.model_dump(mode="json"),
                },
            )
            state.providers.append(provider_name)
            return f"Created {len(state.draft.sections)} structured sections."
        if tool == ToolName.RENDER_DOCUMENT:
            if state.draft is None:
                raise AgentExecutionError("No validated draft exists to render.")
            name = safe_document_name(state.draft.title, job_id)
            destination = self._settings.output_dir / name
            render_docx(state.draft, destination)
            state.destination = destination
            return f"Saved the final Word document as {name}."
        raise AgentExecutionError(f"Unsupported tool rejected by allowlist: {tool}")

    async def _generate_model(
        self,
        *,
        model: type[ModelT],
        operation: str,
        system_prompt: str,
        payload: dict[str, Any],
    ) -> tuple[ModelT, str]:
        result = await self._provider.generate_json(
            operation=operation,
            system_prompt=system_prompt,
            payload=payload,
            response_schema=model.model_json_schema(mode="validation"),
        )
        return model.model_validate(result.data), result.provider

    @staticmethod
    def _dependencies_satisfied(task: PlannedTask, state: ExecutionState) -> bool:
        completed = {
            execution.id
            for execution in state.executions
            if execution.status == "completed"
        }
        return set(task.depends_on).issubset(completed)

