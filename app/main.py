from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from app.agent import AgentExecutionError, DocumentAgent
from app.config import Settings
from app.json_compat import MultilineJsonStringRoute
from app.llm import LLMProvider, build_provider
from app.schemas import AgentRequest, AgentResponse, HealthResponse

def create_app(
    settings: Settings | None = None, provider: LLMProvider | None = None
) -> FastAPI:
    runtime_settings = settings or Settings.from_env()
    runtime_provider = provider or build_provider(runtime_settings)
    agent = DocumentAgent(runtime_settings, runtime_provider)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        runtime_settings.output_dir.mkdir(parents=True, exist_ok=True)
        yield

    app = FastAPI(
        title=runtime_settings.app_name,
        version="2.0.0",
        description=(
            "A Gemini-powered autonomous agent that plans and renders guarded "
            "Microsoft Word documents."
        ),
        lifespan=lifespan,
    )
    app.router.route_class = MultilineJsonStringRoute

    @app.exception_handler(AgentExecutionError)
    async def agent_error_handler(
        _: Request, exc: AgentExecutionError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": "agent_execution_failed",
                "detail": str(exc),
                "recoverable": True,
            },
        )

    @app.get("/health", response_model=HealthResponse, tags=["operations"])
    async def health() -> HealthResponse:
        return HealthResponse(
            model=runtime_settings.gemini_model,
            api_key_configured=bool(runtime_settings.gemini_api_key),
        )

    @app.post("/agent", response_model=AgentResponse, tags=["agent"])
    async def run_agent(payload: AgentRequest, request: Request) -> AgentResponse:
        base_url = str(request.base_url).rstrip("/")
        return await agent.run(payload.request, base_url=base_url)

    @app.get("/documents/{document_name}", tags=["documents"])
    async def download_document(document_name: str) -> Response:
        if (
            Path(document_name).name != document_name
            or not document_name.endswith(".docx")
        ):
            raise HTTPException(status_code=400, detail="Invalid document name.")
        destination = runtime_settings.output_dir / document_name
        if not destination.is_file():
            raise HTTPException(status_code=404, detail="Document not found.")
        return Response(
            content=destination.read_bytes(),
            media_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
            headers={"Content-Disposition": f'attachment; filename="{document_name}"'},
        )

    return app

app = create_app()
