# Sandbox runner for Python submissions.
# Runs with: no network, all capabilities dropped, read-only rootfs,
# non-root user. Analyzer versions are pinned so findings are reproducible.
FROM python:3.12-slim

RUN pip install --no-cache-dir \
        ruff==0.15.21 \
        bandit==1.9.4 \
        radon==6.0.1 \
        semgrep==1.170.0 \
    && rm -rf /root/.cache

COPY harness/entrypoint.py /opt/runner/entrypoint.py
COPY rules/semgrep/python /opt/rules/python

# The submission is injected into /work before the container starts.
RUN mkdir -p /work && chown 65534:65534 /work /opt/runner/entrypoint.py

USER 65534:65534
WORKDIR /work

# Tool caches must live on the writable tmpfs, the rootfs is read-only.
ENV HOME=/tmp \
    TMPDIR=/tmp \
    XDG_CACHE_HOME=/tmp/.cache \
    RUFF_CACHE_DIR=/tmp/.ruff_cache \
    SEMGREP_USER_AGENT_APPEND=codeguide-runner \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["python3", "/opt/runner/entrypoint.py"]
