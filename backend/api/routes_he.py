from fastapi import APIRouter, HTTPException
from backend.api.schemas import HESearchRequest, HESearchResponse, HETiming, HEResultItem
from backend.defenses.he_search.encrypted_search import encrypted_search

router = APIRouter(prefix="/api/he", tags=["homomorphic"])


@router.post("/search", response_model=HESearchResponse)
async def he_search_endpoint(req: HESearchRequest) -> HESearchResponse:
    try:
        result = encrypted_search(query=req.query, top_k=req.top_k)
        return HESearchResponse(
            results=[HEResultItem(**r) for r in result.results],
            timing=HETiming(**result.timing),
            plaintext_results=[HEResultItem(**r) for r in result.plaintext_results],
            plaintext_timing_ms=result.plaintext_timing_ms,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Encrypted search failed: {e}")
