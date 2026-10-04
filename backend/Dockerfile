# syntax=docker/dockerfile:1
FROM python:3.12-slim AS build

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim

# curl is used by the container healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /install /usr/local
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic

# Non-root, but a member of the docker group so it can reach the mounted
# docker socket to launch sandbox containers (compose mode). DOCKER_GID must
# match the host socket's group (the Makefile passes it in).
ARG DOCKER_GID=999
RUN useradd -m -u 10001 app \
    && if ! getent group "${DOCKER_GID}" >/dev/null; then \
         groupadd -g "${DOCKER_GID}" docker; \
       fi \
    && usermod -aG "$(getent group "${DOCKER_GID}" | cut -d: -f1)" app
USER app

ENV PYTHONUNBUFFERED=1 \
    CODEGUIDE_DATABASE_URL=sqlite+aiosqlite:///./data/app.db

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:8000/readyz || exit 1

CMD ["uvicorn", "codeguide.main:app", "--host", "0.0.0.0", "--port", "8000"]
