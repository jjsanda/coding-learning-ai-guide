"""Application configuration.

Every knob is environment-driven with safe defaults: a fresh checkout runs
with zero configuration (SQLite, Docker execution backend, template feedback).
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CODEGUIDE_", env_file=".env", extra="ignore")

    # --- server ---
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]

    # --- database ---
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    # --- submission limits ---
    max_files_per_submission: int = 20
    max_submission_bytes: int = 200_000
    submission_rate_limit_per_minute: int = 6

    # --- execution backend ---
    execution_backend: Literal["docker", "kubernetes", "local"] = "docker"
    allow_unsafe_local: bool = False
    worker_concurrency: int = 2
    sandbox_wall_timeout_s: int = 120
    sandbox_memory_mb: int = 512
    sandbox_cpus: float = 1.0
    sandbox_pids_limit: int = 128
    runner_image_python: str = "coding-learning-ai-guide-runner-python:latest"
    runner_image_node: str = "coding-learning-ai-guide-runner-node:latest"

    # --- kubernetes backend ---
    k8s_sandbox_namespace: str = "clag-sandbox"
    k8s_active_deadline_s: int = 180
    k8s_gvisor_runtime_class: str | None = None
    # Runner images are deployed to the cluster alongside the app, so pods
    # should use the local image rather than re-pulling from a registry.
    k8s_runner_pull_policy: str = "IfNotPresent"

    # --- feedback providers ---
    feedback_provider: Literal["auto", "anthropic", "openai", "ollama", "template"] = "auto"
    anthropic_model: str = "claude-opus-4-8"
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str | None = None
    ollama_model: str = "llama3.1"
    feedback_timeout_s: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
