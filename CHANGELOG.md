# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Student submission flow: join a course, submit Python or JavaScript, and
  receive formative feedback on correctness, style, complexity and security.
- Sandboxed execution with no network, a read-only root filesystem, dropped
  capabilities and resource limits, on both a Docker and a Kubernetes Jobs
  backend (plus an unsafe local backend for CI).
- Deterministic analyzers — Ruff, Bandit, radon and Semgrep for Python; ESLint
  and Semgrep for JavaScript — normalized into a single finding schema and
  mapped to a misconception taxonomy.
- Multi-provider feedback (Anthropic, OpenAI, Ollama) with a deterministic
  template fallback, so the tool works with no API key.
- Instructor dashboard aggregating class-wide misconceptions, pass rates and
  finding categories from deterministic analyzer output.
- One-command Docker Compose demo, a Helm chart with NetworkPolicies and an
  optional gVisor RuntimeClass, and a scripted kind-cluster demo.
