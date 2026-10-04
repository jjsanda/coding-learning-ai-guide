# Sandbox runner for JavaScript submissions.
# Runs with: no network, all capabilities dropped, read-only rootfs,
# non-root user. Analyzer versions are pinned so findings are reproducible.
FROM node:22-slim

# The harness is Python and semgrep is a Python tool; install a minimal
# Python alongside Node.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir --break-system-packages semgrep==1.170.0

# eslint lives in /opt/runner/node_modules so the flat config (ESM) can
# resolve its plugins; global npm installs are not importable from a config.
WORKDIR /opt/runner
RUN npm init -y >/dev/null \
    && npm install --no-fund --no-audit \
        eslint@10.7.0 \
        eslint-plugin-security@4.0.1 \
    && npm cache clean --force
ENV PATH=/opt/runner/node_modules/.bin:$PATH

COPY harness/entrypoint.py /opt/runner/entrypoint.py
COPY node/eslint.config.mjs /opt/runner/eslint.config.mjs
COPY rules/semgrep/javascript /opt/rules/javascript

RUN mkdir -p /work && chown 65534:65534 /work

USER 65534:65534
WORKDIR /work

ENV HOME=/tmp \
    TMPDIR=/tmp \
    XDG_CACHE_HOME=/tmp/.cache \
    SEMGREP_USER_AGENT_APPEND=codeguide-runner \
    NODE_OPTIONS=--max-old-space-size=256

ENTRYPOINT ["python3", "/opt/runner/entrypoint.py"]
