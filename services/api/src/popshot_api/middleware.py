"""Per-request logging context and response headers.

Logs method, route path, status and duration. Never logs query strings, headers or bodies,
because those can carry tokens or invite codes.
"""

import re
import time
import uuid

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = structlog.get_logger("popshot_api.request")

# Cloud Run sends "TRACE_ID/SPAN_ID;o=1". Only accept the expected shape.
_TRACE_RE = re.compile(r"^([0-9a-f]{32})(?:/\d{1,20})?(?:;o=[01])?$")

_SECURITY_HEADERS = [
    (b"cache-control", b"no-store"),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
]


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        structlog.contextvars.clear_contextvars()
        context: dict[str, str] = {"request_id": uuid.uuid4().hex}
        for name, value in scope["headers"]:
            if name == b"x-cloud-trace-context":
                match = _TRACE_RE.match(value.decode("latin-1"))
                if match:
                    context["trace_id"] = match.group(1)
                break
        structlog.contextvars.bind_contextvars(**context)

        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message["headers"] = [*message.get("headers", []), *_SECURITY_HEADERS]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            log.exception("request.failed", method=scope["method"], path=scope["path"])
            raise
        finally:
            log.info(
                "request",
                method=scope["method"],
                path=scope["path"],
                status=status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            structlog.contextvars.clear_contextvars()
