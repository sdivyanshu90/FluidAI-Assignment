from __future__ import annotations

from typing import Any
from app.llm.providers import GenerationResult

class FakeGeminiProvider:
    """Deterministic test double; it is not a local language model."""

    async def generate_json(
        self,
        *,
        operation: str,
        system_prompt: str,
        payload: dict[str, Any],
        response_schema: dict[str, Any],
    ) -> GenerationResult:
        assert system_prompt
        assert response_schema["type"] == "object"
        if operation == "plan":
            data = self._plan(str(payload["request"]))
        elif operation == "draft":
            data = self._draft(payload["brief"])
        else:
            raise AssertionError(f"unexpected operation: {operation}")
        return GenerationResult(data=data, provider="gemini/test-double")

    @staticmethod
    def _plan(request: str) -> dict[str, Any]:
        complex_request = any(
            marker in request.lower()
            for marker in ("missing", "conflicting", "no confirmed", "ambiguous")
        )
        assumptions = [
            "Dates and owners remain planning assumptions until stakeholder approval."
        ]
        tasks = [
            {
                "id": "task_analyze",
                "title": "Analyze request",
                "tool": "analyze_request",
                "description": "Identify purpose, audience, scope, and constraints.",
                "depends_on": [],
            }
        ]
        previous = "task_analyze"
        if complex_request:
            assumptions.append(
                "Conflicting requirements will be resolved through a phased rollout."
            )
            tasks.append(
                {
                    "id": "task_assumptions",
                    "title": "Record assumptions",
                    "tool": "record_assumptions",
                    "description": "Make missing and conflicting requirements explicit.",
                    "depends_on": [previous],
                }
            )
            previous = "task_assumptions"
        tasks.extend(
            [
                {
                    "id": "task_draft",
                    "title": "Draft document",
                    "tool": "draft_document",
                    "description": "Create the complete structured business document.",
                    "depends_on": [previous],
                },
                {
                    "id": "task_render",
                    "title": "Render Word document",
                    "tool": "render_document",
                    "description": "Create the final DOCX artifact.",
                    "depends_on": ["task_draft"],
                },
            ]
        )
        return {
            "brief": {
                "title": "Customer Onboarding Delivery Plan",
                "document_type": "Project Plan",
                "audience": "Executive leadership and delivery stakeholders",
                "purpose": request,
                "goals": [
                    "Define an executable delivery approach.",
                    "Make ownership and success measures explicit.",
                ],
                "constraints": ["Complete within the requested timeline."],
                "assumptions": assumptions,
            },
            "tasks": tasks,
        }

    @staticmethod
    def _draft(brief: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": brief["title"],
            "subtitle": "Guarded autonomous-agent output",
            "audience": brief["audience"],
            "executive_summary": (
                "This document converts the validated request into a phased, accountable "
                "delivery approach with explicit risks, measures, and assumptions."
            ),
            "sections": [
                {
                    "heading": "Objectives and Scope",
                    "paragraphs": ["The initiative aligns delivery activities to measurable outcomes."],
                    "bullets": brief["goals"],
                    "table": None,
                },
                {
                    "heading": "Delivery Plan",
                    "paragraphs": ["Delivery proceeds through controlled phases."],
                    "bullets": [],
                    "table": {
                        "title": "Phased plan",
                        "headers": ["Phase", "Owner", "Exit criterion"],
                        "rows": [
                            ["Discover", "Project lead", "Requirements approved"],
                            ["Deliver", "Delivery team", "Acceptance tests passed"],
                        ],
                    },
                },
                {
                    "heading": "Risks and Next Steps",
                    "paragraphs": ["Risks are reviewed at each governance checkpoint."],
                    "bullets": ["Confirm owners.", "Approve scope.", "Schedule kickoff."],
                    "table": {
                        "title": "Initial risks",
                        "headers": ["Risk", "Mitigation"],
                        "rows": [["Unclear scope", "Approve acceptance criteria early"]],
                    },
                },
            ],
            "assumptions": brief["assumptions"],
        }

