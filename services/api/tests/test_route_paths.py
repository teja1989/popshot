"""Every route the browser can reach fits the web's proxy (apps/web/src/lib/bff.ts): at most
MAX_SEGMENTS path segments, each plain letters, digits, '-' and '_' (no dots). A route that
doesn't would only fail through the proxy, never in these API tests."""

import re

from popshot_api.admin_main import create_admin_app
from popshot_api.main import create_app
from tests.conftest import make_settings
from tests.fakes import FakeTokenVerifier

MAX_SEGMENTS = 8
SEGMENT = re.compile(r"^([A-Za-z0-9_-]{1,64}|\{[a-z_]+\})$")


def test_every_route_fits_the_web_proxy() -> None:
    too_long = []
    for app in (
        create_app(make_settings(), FakeTokenVerifier(), verify_database_role=False),
        create_admin_app(make_settings(), FakeTokenVerifier(), verify_database_role=False),
    ):
        # Every route's full path, as the API serves it.
        paths = [p for p in app.openapi()["paths"] if p.startswith("/v1/")]
        assert len(paths) > 10
        for path in paths:
            segments = path.strip("/").split("/")
            if len(segments) > MAX_SEGMENTS or not all(SEGMENT.match(s) for s in segments):
                too_long.append(path)
    assert too_long == []
