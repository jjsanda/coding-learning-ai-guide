# Deployment

Three ways to run coding-learning-ai-guide, from quickest to most production-like:

| Path | Command | Use for |
|---|---|---|
| **Docker Compose** | `make demo` | Local development and the one-command demo |
| **Kubernetes (kind)** | `make kind-demo` | A full cluster walkthrough on your laptop |
| **Helm** | `helm install codeguide deploy/helm/coding-learning-ai-guide` | Real clusters |

All three run the same code; what changes is the *execution backend* the API
uses to sandbox student submissions (`CODEGUIDE_EXECUTION_BACKEND`): Docker
containers in Compose mode, Kubernetes Jobs in cluster mode.

---

## Docker Compose

### What `make demo` does

```bash
make demo
```

Step by step (see the [Makefile](../Makefile) and
[docker-compose.yml](../docker-compose.yml)):

1. **Builds the sandbox runner images** (`make runners`):
   `coding-learning-ai-guide-runner-python:latest` and
   `coding-learning-ai-guide-runner-node:latest`, from
   `runners/python/Dockerfile` and `runners/node/Dockerfile`. These are the
   images student code runs *inside*; they are launched per-submission and are
   not Compose services, which is why they're built separately.
2. **Computes the host Docker socket's group ID**:
   `stat -c '%g' /var/run/docker.sock` (falling back to `999`). It's passed as
   the `DOCKER_GID` build argument of the API image so the non-root API user is
   in the right group to talk to the mounted socket.
3. **Starts the stack**: `docker compose up -d --build --wait` brings up three
   services —
   - `db` — Postgres 16 with a healthcheck,
   - `api` — the FastAPI orchestrator on port **8000**, configured with
     `CODEGUIDE_EXECUTION_BACKEND=docker` and the Postgres URL,
   - `web` — the frontend on port **8080**, proxying `/api` to the API.
4. **Seeds demo data**: `docker compose exec -T api python -m codeguide.cli seed`
   creates two demo courses with assignments and real analyzed submissions,
   then prints the course **join codes** and an **instructor token**.

Then open <http://localhost:8080> (web app) and
<http://localhost:8000/api/docs> (interactive API docs).

### How the sandbox works in Compose mode

The `api` service mounts the host Docker socket:

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

For every submission, the API asks the **host** Docker daemon to launch a
short-lived runner container with `network_disabled` (no network interface at
all), a read-only root filesystem, tmpfs-only writable paths, non-root user,
all capabilities dropped, `no-new-privileges`, and memory/CPU/pid limits plus a
wall-clock timeout (see
[`backend/src/codeguide/execution/docker_backend.py`](../backend/src/codeguide/execution/docker_backend.py)).
The submission is streamed to the container over stdin as a gzipped payload and
the result comes back on stdout — the sandbox never gets a network socket.

Be aware of the trade-off: access to the Docker socket is root-equivalent *on
the host*, so Compose mode trusts the API container. This is fine for local use
and development; for multi-tenant or production deployments prefer the
Kubernetes backend, where the API only holds a narrowly-scoped RBAC role. The
[security model](security-model.md) discusses this residual risk.

### Enabling LLM feedback

The demo runs entirely on the built-in deterministic feedback templates — no
API key required. To get LLM-written explanations:

```bash
cp .env.example .env
# edit .env:
#   ANTHROPIC_API_KEY=sk-ant-...      (or OPENAI_API_KEY=...)
docker compose up -d      # recreate the api container with the key
```

`docker-compose.yml` forwards `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` from
`.env` into the `api` container. The feedback provider is `auto` by default:
it picks the first configured of Anthropic / OpenAI / Ollama, else templates.
You can pin one with `CODEGUIDE_FEEDBACK_PROVIDER`, and pick models with
`CODEGUIDE_ANTHROPIC_MODEL` / `CODEGUIDE_OPENAI_MODEL` (see
[.env.example](../.env.example) and
[`config.py`](../backend/src/codeguide/config.py) for every knob).

> **Note (Ollama):** the Compose file only forwards the two API-key variables.
> To use a local Ollama server, add `CODEGUIDE_OLLAMA_BASE_URL` (and optionally
> `CODEGUIDE_OLLAMA_MODEL`) to the `api` service's `environment` in
> `docker-compose.yml`.

The `/api/v1/meta` endpoint (and the web UI footer) shows which provider is
actually active.

### Resetting

```bash
make clean
```

runs `docker compose down -v --remove-orphans` (stops the stack and deletes the
Postgres volume) and removes `backend/data` (the local SQLite directory used
outside Compose). Re-run `make demo` for a fresh stack, or `make seed` to just
re-seed a running one.

---

## Kubernetes with Helm

```bash
helm install codeguide deploy/helm/coding-learning-ai-guide
```

The chart deploys:

- the **API** Deployment + Service (with `CODEGUIDE_EXECUTION_BACKEND=kubernetes`),
- the **web** Deployment + Service,
- an in-chart **Postgres** StatefulSet (optional; bring your own by disabling it),
- a dedicated **sandbox namespace** with a default-deny NetworkPolicy,
- **RBAC** limiting the API's ServiceAccount to managing Jobs/ConfigMaps/pod
  logs *only inside the sandbox namespace*,
- optionally a **gVisor RuntimeClass** and an **Ingress**.

Per submission, the API creates a Kubernetes **Job** in the sandbox namespace
using the runner image for the assignment's language, reads the result from the
pod logs, and deletes the Job.

### Images

The image registry defaults to `ghcr.io/jjsanda`. The chart does **not** build
anything: the four images (`coding-learning-ai-guide-api`, `-web`,
`-runner-python`, `-runner-node`) must already be pushed to a registry your
nodes can pull from — or pre-loaded onto the nodes (as the kind demo does with
`kind load docker-image`) with `image.pullPolicy=IfNotPresent`. Override with:

```bash
helm install codeguide deploy/helm/coding-learning-ai-guide \
  --set image.registry=registry.example.com/codeguide \
  --set image.tag=v0.1.0
```

### Values reference

From [`deploy/helm/coding-learning-ai-guide/values.yaml`](../deploy/helm/coding-learning-ai-guide/values.yaml):

| Value | Default | Meaning |
|---|---|---|
| `image.registry` | `ghcr.io/jjsanda` | Registry prefix for all four images |
| `image.tag` | `latest` | Tag for all four images |
| `image.pullPolicy` | `IfNotPresent` | Pull policy for app images *and* sandbox runner pods |
| `api.image` | `coding-learning-ai-guide-api` | API image name |
| `api.replicas` | `1` | API replica count |
| `api.workerConcurrency` | `2` | Concurrent sandbox runs per API pod (`CODEGUIDE_WORKER_CONCURRENCY`) |
| `api.resources` | 100m/256Mi requests, 1/512Mi limits | API container resources |
| `api.llmSecretName` | `""` | Name of a Secret injected via `envFrom`; empty = template feedback |
| `web.image` | `coding-learning-ai-guide-web` | Web image name |
| `web.replicas` | `1` | Web replica count |
| `runners.python` | `coding-learning-ai-guide-runner-python` | Python sandbox image name |
| `runners.node` | `coding-learning-ai-guide-runner-node` | JavaScript sandbox image name |
| `sandbox.namespace` | `clag-sandbox` | Namespace sandbox Jobs run in (created by the chart) |
| `sandbox.wallTimeoutSeconds` | `120` | Orchestrator-side wall-clock limit per run |
| `sandbox.activeDeadlineSeconds` | `180` | Kubernetes `activeDeadlineSeconds` on sandbox Jobs |
| `sandbox.memoryMb` | `512` | Memory limit per sandbox pod |
| `sandbox.cpus` | `1` | CPU limit per sandbox pod |
| `sandbox.gvisor.enabled` | `false` | Create a RuntimeClass and run sandbox Jobs under gVisor |
| `sandbox.gvisor.runtimeClassName` | `gvisor` | RuntimeClass name **and** containerd handler name |
| `postgres.enabled` | `true` | Deploy the in-chart Postgres (disable to bring your own via `CODEGUIDE_DATABASE_URL`) |
| `postgres.image` | `postgres:16-alpine` | Postgres image |
| `postgres.user` / `postgres.password` / `postgres.database` | `codeguide` | Credentials — **change the password** for anything non-local |
| `postgres.storage` | `1Gi` | PersistentVolumeClaim size |
| `ingress.enabled` | `false` | Create an Ingress |
| `ingress.className` | `""` | `ingressClassName` (empty = cluster default) |
| `ingress.host` | `codeguide.local` | Ingress host |

### LLM feedback on Kubernetes

Put the provider key in a Secret and point `api.llmSecretName` at it. Every
key in the Secret becomes an environment variable in the API container
(`envFrom: secretRef`), so use the exact variable names from
[.env.example](../.env.example):

```bash
kubectl create secret generic codeguide-llm \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-...

helm upgrade --install codeguide deploy/helm/coding-learning-ai-guide \
  --set api.llmSecretName=codeguide-llm
```

Leave `llmSecretName` empty and the stack runs on deterministic feedback
templates — fully offline.

### Ingress

Off by default; the kind demo uses `kubectl port-forward` instead. To expose
the stack through an ingress controller:

```bash
helm upgrade --install codeguide deploy/helm/coding-learning-ai-guide \
  --set ingress.enabled=true \
  --set ingress.className=nginx \
  --set ingress.host=codeguide.example.edu
```

The Ingress routes `/api` to the API Service (port 8000) and everything else
to the web Service (port 80). TLS is not templated — add it with your
cluster's usual mechanism (e.g. cert-manager annotations on a wrapper, or a
fork of `templates/ingress.yaml`).

### Seeding and creating instructors on a cluster

There is no signup endpoint; use the CLI inside an API pod:

```bash
API_POD=$(kubectl get pod -l codeguide.io/component=api -o jsonpath='{.items[0].metadata.name}')
kubectl exec "$API_POD" -- python -m codeguide.cli seed
kubectl exec "$API_POD" -- python -m codeguide.cli create-instructor \
  --name "Ada Lovelace" --email ada@example.edu
```

---

## The kind walkthrough

```bash
make kind-demo        # runs deploy/kind/demo.sh
```

Requires `kind`, `kubectl`, `helm` and `docker`. The script
([deploy/kind/demo.sh](../deploy/kind/demo.sh)):

1. **Builds** all four images locally (`make runners`, plus the API and web
   images).
2. **Creates a kind cluster** named `codeguide` (single control-plane node,
   [deploy/kind/kind-config.yaml](../deploy/kind/kind-config.yaml)) — skipped
   if it already exists.
3. **Loads the images into the cluster**, re-tagged under the chart's default
   `ghcr.io/jjsanda/...:latest` names, with `kind load docker-image` — so
   nothing is pulled from a registry.
4. **Installs the Helm chart** (`helm upgrade --install codeguide ...
   --set image.pullPolicy=IfNotPresent --wait`).
5. **Seeds demo data** by exec-ing `python -m codeguide.cli seed` in the API
   pod — the seeded submissions are analyzed in real Kubernetes sandbox Jobs.
6. **Port-forwards** the web Service to <http://localhost:8080>.
7. **Runs the smoke test** ([scripts/smoke.sh](../scripts/smoke.sh)): joins a
   course over the public API, submits deliberately problematic code, polls
   until the sandbox Job completes and asserts that feedback comes back.
8. **Verifies isolation** by checking the `sandbox-deny-all` NetworkPolicy
   exists in the sandbox namespace.

The stack stays up (Ctrl-C stops the port-forward). Tear it down with:

```bash
kind delete cluster --name codeguide
```

> **Note:** the kind demo runs sandbox Jobs with the node's default runtime
> (**runc**). gVisor is *not* installed on kind's stock node images, so the
> demo does not exercise the gVisor path — see below.

---

## gVisor (optional, defense in depth)

For kernel-level isolation of student code, sandbox Jobs can run under
[gVisor](https://gvisor.dev/) (`runsc`), a user-space kernel that intercepts
syscalls so untrusted code never talks to the host kernel directly.

Enable it in the chart:

```bash
helm upgrade --install codeguide deploy/helm/coding-learning-ai-guide \
  --set sandbox.gvisor.enabled=true \
  --set sandbox.gvisor.runtimeClassName=gvisor
```

This makes the chart create a `RuntimeClass` whose `handler` equals
`runtimeClassName`, and the API sets that RuntimeClass on every sandbox Job
(`CODEGUIDE_K8S_GVISOR_RUNTIME_CLASS`).

**What the chart does *not* do:** install gVisor. You need, on every node that
can schedule sandbox pods:

1. the `runsc` binary and its containerd shim installed, and
2. a containerd runtime handler with the same name as `runtimeClassName`
   (e.g. `[plugins."io.containerd.grpc.v1.cri".containerd.runtimes.gvisor]`
   with `runtime_type = "io.containerd.runsc.v1"`).

Follow the gVisor project's guides:
[containerd quick start](https://gvisor.dev/docs/user_guide/containerd/quick_start/)
and [Kubernetes](https://gvisor.dev/docs/user_guide/quick_start/kubernetes/).
Managed offerings (e.g. GKE Sandbox) ship this preinstalled.

**Honesty note:** the gVisor path is templated and configured but is *not*
exercised by this repository's automated demo — kind's node image doesn't ship
gVisor, so `make kind-demo` runs with runc. If you enable it, verify on your
cluster that a sandbox pod actually gets the runtime, e.g.:

```bash
kubectl -n clag-sandbox get pod -o jsonpath='{.items[*].spec.runtimeClassName}'
```

Without gVisor the sandbox still has meaningful isolation — no network,
non-root, read-only rootfs, dropped capabilities, seccomp `RuntimeDefault`,
resource limits and a default-deny NetworkPolicy — gVisor adds a second wall.
