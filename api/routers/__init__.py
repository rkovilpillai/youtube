"""
API Routers package initialization.
Exports all router instances for main app inclusion.
"""
from api.routers.campaigns import router as campaigns_router
from api.routers.keywords import router as keywords_router
from api.routers.youtube import router as youtube_router
from api.routers.scoring import router as scoring_router
from api.routers.transcript import router as transcript_router

__all__ = [
    "campaigns_router",
    "keywords_router",
    "youtube_router",
    "scoring_router",
    "transcript_router",
]
