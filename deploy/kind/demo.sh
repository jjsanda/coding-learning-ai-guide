#!/usr/bin/env bash
# Stand up the whole stack on a local kind cluster and smoke-test the
# Kubernetes Jobs sandbox backend end to end.
#
#   Requires: kind, kubectl, helm, docker.
#   Run from the repository root:  bash deploy/kind/demo.sh
set -euo pipefail

CLUSTER=codeguide
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REGISTRY=ghcr.io/jjsanda
TAG=latest
IMAGES=(
  "coding-learning-ai-guide-api"
  "coding-learning-ai-guide-web"
  "coding-learning-ai-guide-runner-python"
  "coding-learning-ai-guide-runner-node"
)

log() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }

log "Building images"
make -C "$ROOT" runners
docker build -t coding-learning-ai-guide-api:latest "$ROOT/backend"
docker build -t coding-learning-ai-guide-web:latest "$ROOT/frontend"

log "Creating kind cluster '$CLUSTER'"
if ! kind get clusters | grep -qx "$CLUSTER"; then
  kind create cluster --config "$ROOT/deploy/kind/kind-config.yaml"
fi
kubectl config use-context "kind-$CLUSTER"

log "Loading images into the cluster"
for img in "${IMAGES[@]}"; do
  # Tag under the chart's registry prefix so the in-cluster pods find them.
  docker tag "${img}:latest" "${REGISTRY}/${img}:${TAG}"
  kind load docker-image "${REGISTRY}/${img}:${TAG}" --name "$CLUSTER"
done

log "Installing the Helm chart"
helm upgrade --install codeguide "$ROOT/deploy/helm/coding-learning-ai-guide" \
  --set image.pullPolicy=IfNotPresent \
  --wait --timeout 5m

log "Waiting for the API to be ready"
kubectl rollout status deployment/codeguide-api --timeout=180s

log "Seeding demo data (runs submissions as Kubernetes Jobs)"
API_POD=$(kubectl get pod -l codeguide.io/component=api -o jsonpath='{.items[0].metadata.name}')
SEED_OUT=$(kubectl exec "$API_POD" -- python -m codeguide.cli seed 2>/dev/null)
echo "$SEED_OUT"
# Join codes are printed as "  CODE   Course title" lines.
JOIN_CODE=$(echo "$SEED_OUT" | grep -E '^  [A-Z0-9]{8}   ' | head -1 | awk '{print $1}')
[ -n "$JOIN_CODE" ] || { echo "could not find a join code in seed output"; exit 1; }

log "Port-forwarding the web app to http://localhost:8080"
kubectl port-forward svc/codeguide-web 8080:80 >/dev/null 2>&1 &
PF_PID=$!
trap 'kill $PF_PID 2>/dev/null || true' EXIT
sleep 3

log "Running the smoke test against the Kubernetes-backed stack (join code $JOIN_CODE)"
bash "$ROOT/scripts/smoke.sh" http://localhost:8080 "$JOIN_CODE" \
  || { log "Smoke test failed — dumping recent sandbox Jobs"; kubectl -n clag-sandbox get jobs; exit 1; }

log "Verifying sandbox isolation"
kubectl -n clag-sandbox get networkpolicy sandbox-deny-all >/dev/null && echo "  ✓ default-deny NetworkPolicy present"

log "Done. The stack is live; press Ctrl-C to stop the port-forward."
echo "  Web UI:  http://localhost:8080"
echo "  Tear down with: kind delete cluster --name $CLUSTER"
wait $PF_PID
