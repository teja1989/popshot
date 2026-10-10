# Popshot API image. Base images are pinned by digest; Dependabot keeps them current.

FROM python:3.13-slim@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f AS build
# uv from its GitHub release; BuildKit checks the SHA-256 before using it (same as CI).
ADD --checksum=sha256:aab924fd522efd06f1c5f3b93a243864fc453132c94b2dc49f1371b528a4b967 \
    https://github.com/astral-sh/uv/releases/download/0.11.32/uv-x86_64-unknown-linux-gnu.tar.gz \
    /tmp/uv.tar.gz
RUN tar -xzf /tmp/uv.tar.gz -C /usr/local/bin --strip-components=1 \
 && rm /tmp/uv.tar.gz \
 && uv --version
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src
# Dependencies first, so code changes don't invalidate this layer.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project --no-editable
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.13-slim@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f AS runtime
# pip (and its vendored libraries) and ensurepip aren't needed at runtime; the app lives in
# its own venv. Removing them takes their CVEs out of the image.
RUN rm -rf /usr/local/lib/python3.13/site-packages/pip \
           /usr/local/lib/python3.13/site-packages/pip-*.dist-info \
           /usr/local/lib/python3.13/ensurepip \
           /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.13 \
 && groupadd --system --gid 10001 popshot \
 && useradd --system --uid 10001 --gid popshot --no-create-home --shell /usr/sbin/nologin popshot
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
# Migrations ship in the same image; the migrate job runs `alembic upgrade head`.
COPY alembic.ini ./
COPY migrations ./migrations
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER 10001:10001
EXPOSE 8080
# Cloud Run sends traffic to 8080. Access logs come from our own middleware.
CMD ["uvicorn", "--factory", "popshot_api.main:create_app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log", "--no-server-header"]
