from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi.routing import APIRoute
from starlette.requests import Request
from starlette.responses import Response


def normalize_multiline_json_strings(body: bytes) -> bytes:
    """Replace illegal literal newlines inside JSON strings with a single space.

    This supports terminal commands where a long quoted request is wrapped across
    lines. It does not change JSON whitespace outside strings or escaped ``\\n``.
    """

    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return body

    normalized: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        character = text[index]
        if in_string and character in {"\r", "\n"}:
            normalized.append(" ")
            if character == "\r" and index + 1 < len(text) and text[index + 1] == "\n":
                index += 1
            escaped = False
        else:
            normalized.append(character)
            if character == "\\" and in_string:
                escaped = not escaped
            else:
                if character == '"' and not escaped:
                    in_string = not in_string
                escaped = False
        index += 1
    return "".join(normalized).encode("utf-8")


class MultilineJsonStringRoute(APIRoute):
    """Compatibility route that repairs terminal-wrapped JSON string literals."""

    def get_route_handler(
        self,
    ) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original_handler = super().get_route_handler()

        async def handler(request: Request) -> Response:
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                body = await request.body()
                normalized = normalize_multiline_json_strings(body)
                if normalized != body:
                    # Starlette caches `body()` on the request. Updating that cache lets
                    # FastAPI retain its usual typed request parsing and 422 responses.
                    request._body = normalized  # type: ignore[attr-defined]
            return await original_handler(request)

        return handler
