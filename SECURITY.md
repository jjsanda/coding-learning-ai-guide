# Security Policy

## Reporting a vulnerability

If you find a security vulnerability, please report it privately rather than
opening a public issue. Use GitHub's
[private vulnerability reporting](https://github.com/jjsanda/coding-learning-ai-guide/security/advisories/new)
for this repository.

Please include a description, reproduction steps, and the impact you observed.
You can expect an acknowledgement within a few days.

## Scope

This project executes untrusted student code in a sandbox, so the security of
that sandbox is the primary concern. The [threat model](docs/security-model.md)
documents the controls and — importantly — the **residual risks** we know
about, including the Docker-socket trust concession in Compose mode and the
shared-kernel exposure when gVisor is not enabled.

Reports that demonstrate a sandbox escape, a way for one student to read another
student's submission, or a way to make the orchestrator run attacker-controlled
code are especially valuable.

## Supported versions

This is pre-1.0 software; security fixes land on `main`.
