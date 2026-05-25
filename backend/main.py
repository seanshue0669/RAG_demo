"""FastAPI entrypoint for the Cloud RAG Security Demo backend.

Wires in three domain routers (query, demo, he) and triggers a one-shot
CKKS pre-encryption pass at server startup, so the in-memory EncryptedStore
is ready when the /api/he/search endpoint is first called.

When DEMO_PUBLIC=1 (used by the public cloudflared tunnel deployment):
  - /docs, /redoc, and /openapi.json are disabled
  - Per-IP rate limits are enforced via slowapi
  - The remote-address key uses CF-Connecting-IP when behind cloudflared
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.api import routes_demo, routes_he, routes_query
from backend.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _visitor_ip(request: Request) -> str:
    """Resolve the effective client IP for rate-limiting.

    Behind cloudflared, request.client.host is always 127.0.0.1; the real
    visitor IP is in the CF-Connecting-IP header. Falls back to the direct
    peer when not present.
    """
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip
    if request.client is not None:
        return request.client.host
    return "unknown"


limiter = Limiter(
    key_func=_visitor_ip,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
    enabled=settings.DEMO_PUBLIC,
)


def _warm_up_encrypted_store() -> dict[str, int]:
    """Populate the in-memory EncryptedStore with CKKS-encrypted embeddings.

    Reads the generated JSON corpus, re-embeds in-memory, then encrypts. This
    runs once per process so /api/he/search can serve requests immediately.

    Returns:
        Stats dict: {"records": N, "encrypted": N}. If the corpus is missing,
        returns zeros and logs a warning (the user can run scripts/seed.py).
    """
    from backend.defenses.he_search.encrypted_store import get_encrypted_store
    from backend.embedding.batch_embed import embed_records

    records: list[dict] = []
    for fname in (
        "employees.json",
        "internal_docs.json",
        "public_docs.json",
        "poisoned_docs.json",
    ):
        fp = settings.DATA_GENERATED_DIR / fname
        if fp.exists():
            records.extend(json.loads(fp.read_text(encoding="utf-8")))

    if not records:
        logger.warning(
            "No generated data found in %s — run backend/scripts/seed.py first. "
            "/api/he/search will fail until data is seeded.",
            settings.DATA_GENERATED_DIR,
        )
        return {"records": 0, "encrypted": 0}

    logger.info("Embedding %d documents for HE warm-up...", len(records))
    embedded = embed_records(records)

    logger.info("Pre-encrypting %d embeddings with CKKS...", len(embedded))
    store = get_encrypted_store()
    store.encrypt_all(embedded)

    return {"records": len(records), "encrypted": store.count()}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Server lifespan hook: warm up encrypted store on startup."""
    try:
        stats = _warm_up_encrypted_store()
        logger.info("HE warm-up complete: %s", stats)
        app.state.he_stats = stats
    except Exception as exc:
        logger.exception("HE warm-up failed: %s", exc)
        app.state.he_stats = {"records": 0, "encrypted": 0, "error": str(exc)}
    yield


_docs_kwargs = (
    {"docs_url": None, "redoc_url": None, "openapi_url": None}
    if settings.DEMO_PUBLIC
    else {}
)

app = FastAPI(
    title="Cloud RAG Security Demo",
    description=(
        "Backend for the NovaTech Corp HR RAG security demo. Exposes RAG "
        "query, demo orchestration, and homomorphic-encryption search endpoints."
    ),
    version="0.1.0",
    lifespan=lifespan,
    **_docs_kwargs,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def access_log(request: Request, call_next):
    """Lightweight access log including the visitor IP (CF-aware)."""
    response = await call_next(request)
    logger.info(
        "%s %s %s %s",
        _visitor_ip(request),
        request.method,
        request.url.path,
        response.status_code,
    )
    return response


@app.get("/api/health")
async def health() -> dict:
    """Liveness probe. Reports ChromaDB count and HE store readiness."""
    try:
        from backend.defenses.he_search.encrypted_store import get_encrypted_store
        from backend.vectordb.chroma_store import ChromaStore

        chroma_count = ChromaStore().count()
        he_store = get_encrypted_store()
        return {
            "status": "ok",
            "chroma_doc_count": chroma_count,
            "he_store_ready": he_store.is_ready(),
            "he_store_count": he_store.count(),
        }
    except Exception as exc:
        return {"status": "degraded", "error": str(exc)}


# Routers already declare their own prefixes — include without re-prefixing.
app.include_router(routes_query.router)
app.include_router(routes_demo.router)
app.include_router(routes_he.router)


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=False,
    )
