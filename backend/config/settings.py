"""Central configuration for the Cloud RAG Security Demo backend.

Per CLAUDE.md hard constraint: all paths, URLs, and tunable parameters
MUST be read from this module. Do NOT hardcode these values in other modules.

Environment variables override defaults. Use `get_settings()` to obtain the
singleton instance.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Filesystem layout
# ---------------------------------------------------------------------------
# settings.py lives at: <PROJECT_ROOT>/backend/config/settings.py
# So PROJECT_ROOT is two parents up from this file's parent.
_THIS_FILE = Path(__file__).resolve()
BACKEND_DIR: Path = _THIS_FILE.parent.parent
PROJECT_ROOT: Path = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Application settings.

    All fields can be overridden via environment variables (case-insensitive).
    For example, set `VLLM_BASE_URL=http://localhost:9000/v1` to redirect the
    LLM client. A `.env` file at the project root is also loaded if present.
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------
    PROJECT_ROOT: Path = PROJECT_ROOT
    BACKEND_DIR: Path = BACKEND_DIR
    DATA_DIR: Path = PROJECT_ROOT / "data"
    DATA_GENERATED_DIR: Path = PROJECT_ROOT / "data" / "generated"
    DATA_PRERECORDED_DIR: Path = PROJECT_ROOT / "data" / "prerecorded"
    CHROMA_PERSIST_DIR: Path = BACKEND_DIR / "vectordb" / "db_data"
    TEMPLATES_DIR: Path = BACKEND_DIR / "data_gen" / "templates"

    # ------------------------------------------------------------------
    # Embedding model
    # ------------------------------------------------------------------
    # NOTE: The original spec claims gtr-t5-base is 512-dim — that is incorrect.
    # `sentence-transformers/gtr-t5-base` outputs 768-dimensional embeddings.
    # We use 768 here as the authoritative value across the whole codebase.
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/gtr-t5-base"
    EMBEDDING_DIM: int = 768

    # ------------------------------------------------------------------
    # ChromaDB
    # ------------------------------------------------------------------
    CHROMA_COLLECTION_NAME: str = "hr_documents"

    # ------------------------------------------------------------------
    # vLLM (OpenAI-compatible) endpoint
    # ------------------------------------------------------------------
    # An existing vLLM server is already serving gemma-4-26B-A4B-it on
    # localhost:3053. Override via env var `VLLM_BASE_URL` / `VLLM_MODEL_NAME`
    # if needed.
    VLLM_BASE_URL: str = "http://localhost:3053/v1"
    VLLM_MODEL_NAME: str = "models--google--gemma-4-26B-A4B-it"
    VLLM_TIMEOUT_SECONDS: int = 30

    # ------------------------------------------------------------------
    # Backend server
    # ------------------------------------------------------------------
    # Default binds to localhost only — the FastAPI backend is intentionally
    # NOT directly exposed to the network. Public access is provided through
    # the Vite dev server's /api proxy (or, in production, a cloudflared
    # tunnel pointed at the Vite port). Override via env var if needed.
    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8000

    # ------------------------------------------------------------------
    # Deployment mode
    # ------------------------------------------------------------------
    # When True (set via env var DEMO_PUBLIC=1 for the public tunnel):
    #   - FastAPI's /docs, /redoc, and /openapi.json are disabled
    #   - Slowapi rate-limits are enforced
    #   - Access log is more verbose
    DEMO_PUBLIC: bool = False
    RATE_LIMIT_PER_MINUTE: int = 30

    # ------------------------------------------------------------------
    # CKKS (TenSEAL) parameters
    # ------------------------------------------------------------------
    CKKS_POLY_MODULUS_DEGREE: int = 8192
    CKKS_COEFF_MOD_BIT_SIZES: list[int] = Field(default_factory=lambda: [60, 40, 40, 60])
    CKKS_GLOBAL_SCALE: int = 2 ** 40

    # ------------------------------------------------------------------
    # Data generation volumes
    # ------------------------------------------------------------------
    NUM_EMPLOYEES: int = 50
    NUM_INTERNAL_DOCS: int = 20
    NUM_PUBLIC_DOCS: int = 15
    NUM_POISONED_DOCS: int = 3

    # ------------------------------------------------------------------
    # Role / security-level mapping
    # ------------------------------------------------------------------
    # Per CLAUDE.md: "該角色可存取 security_level <= 自身等級的所有文件".
    ROLE_TO_LEVEL: dict[str, int] = Field(
        default_factory=lambda: {
            "employee": 1,
            "manager": 2,
            "hr_admin": 3,
        }
    )

    # ------------------------------------------------------------------
    # Metadata key constants
    # ------------------------------------------------------------------
    # Single source of truth for ChromaDB metadata field names. All modules
    # must reference these constants instead of hardcoding strings.
    METADATA_KEYS: dict[str, str] = Field(
        default_factory=lambda: {
            "doc_id": "doc_id",
            "doc_type": "doc_type",
            "department": "department",
            "security_level": "security_level",
            "text": "text",
        }
    )

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    def role_to_level(self, role: str) -> int:
        """Return the security level for a given role.

        Args:
            role: One of the keys in `ROLE_TO_LEVEL`.

        Returns:
            The integer security level.

        Raises:
            KeyError: If the role is not recognized.
        """
        return self.ROLE_TO_LEVEL[role]

    def ensure_dirs(self) -> None:
        """Create all directories that the backend expects to exist."""
        for path in (
            self.DATA_DIR,
            self.DATA_GENERATED_DIR,
            self.DATA_PRERECORDED_DIR,
            self.CHROMA_PERSIST_DIR,
            self.TEMPLATES_DIR,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton `Settings` instance.

    The result is cached so configuration is parsed only once per process.
    """
    return Settings()


__all__: list[str] = ["Settings", "get_settings", "PROJECT_ROOT", "BACKEND_DIR"]
