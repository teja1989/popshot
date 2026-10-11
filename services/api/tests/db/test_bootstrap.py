"""The database bootstrap (popshot_api.ops.bootstrap_db)."""

import os

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

from popshot_api.db import use_iam_token_as_password
from popshot_api.ops.bootstrap_db import bootstrap

pytestmark = pytest.mark.db


@pytest.mark.parametrize(
    ("migrator", "api", "database"),
    [
        ("popshot_migrator", "popshot_migrator", "popshot"),
        ('x"; DROP ROLE postgres; --', "popshot_api", "popshot"),
        ("popshot_migrator", "Popshot API", "popshot"),
        ("popshot_migrator", "popshot_api", "popshot; DROP DATABASE x"),
    ],
)
def test_rejects_bad_names_before_connecting(migrator: str, api: str, database: str) -> None:
    with pytest.raises(ValueError, match=r"invalid|different"):
        bootstrap(
            "postgresql://unused@127.0.0.1:1/x", migrator=migrator, api=api, database=database
        )


def test_rerunning_is_safe(migrated: None, owner_engine: Engine) -> None:
    admin_url = os.environ.get("POPSHOT_BOOTSTRAP_ADMIN_URL")
    if not admin_url:
        pytest.skip("POPSHOT_BOOTSTRAP_ADMIN_URL not set")
    database = make_url(str(owner_engine.url)).database or "popshot"
    bootstrap(admin_url, migrator="popshot_migrator", api="popshot_api", database=database)
    bootstrap(admin_url, migrator="popshot_migrator", api="popshot_api", database=database)
    with owner_engine.connect() as conn:
        tables = conn.execute(
            text("SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")
        ).scalar_one()
    assert tables > 10


def test_refuses_unknown_login_user(migrated: None) -> None:
    admin_url = os.environ.get("POPSHOT_BOOTSTRAP_ADMIN_URL")
    if not admin_url:
        pytest.skip("POPSHOT_BOOTSTRAP_ADMIN_URL not set")
    with pytest.raises(RuntimeError, match="doesn't exist"):
        bootstrap(admin_url, migrator="popshot_migrator", api="no_such_user")


def test_iam_token_hook_supplies_the_password(app_url: str, migrated: None) -> None:
    """With IAM auth the URL has no usable password; the hook provides it on each connect."""
    url = make_url(app_url)
    real_password = url.password
    assert real_password
    engine = create_engine(url.set(password="wrong-password"))
    calls: list[int] = []

    def token() -> str:
        calls.append(1)
        return str(real_password)

    use_iam_token_as_password(engine, token)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT current_user")).scalar_one() == url.username
    engine.dispose()
    assert calls == [1]


def test_the_jobs_user_is_separate_too() -> None:
    with pytest.raises(ValueError, match="different"):
        bootstrap(
            "postgresql://unused@127.0.0.1:1/x",
            migrator="popshot_migrator",
            api="popshot_api",
            jobs="popshot_api",
        )


@pytest.mark.parametrize("admin", ["popshot_api", "popshot_migrator"])
def test_the_admin_user_is_separate_too(admin: str) -> None:
    with pytest.raises(ValueError, match="different"):
        bootstrap(
            "postgresql://unused@127.0.0.1:1/x",
            migrator="popshot_migrator",
            api="popshot_api",
            admin=admin,
        )
