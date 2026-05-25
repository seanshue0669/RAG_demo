"""Query route for the RAG API."""

from fastapi import APIRouter, HTTPException

from backend.api.schemas import QueryRequest, QueryResponse
from backend.rag.pipeline import get_pipeline

router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest) -> QueryResponse:
    """Main RAG query endpoint.

    All params (user_role, use_filter, gen_mode, top_k) come from the
    request body.
    """
    try:
        pipeline = get_pipeline()
        return pipeline.run(
            query=req.query,
            user_role=req.user_role,
            use_filter=req.use_filter,
            gen_mode=req.gen_mode,
            top_k=req.top_k,
        )
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Invalid user_role: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
