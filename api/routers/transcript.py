"""Transcript router: exposes video transcript retrieval for frontend debugging."""
from datetime import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from api.database import get_db
from api.models import Campaign, YouTubeVideo
from api.services import youtube_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transcript", tags=["transcript"])


@router.get("/{campaign_id}/{video_id}", response_model=dict)
def get_video_transcript(campaign_id: str, video_id: str, db=Depends(get_db)):
    """Retrieve transcript text for a given campaign/video combination."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": "CAMPAIGN_NOT_FOUND",
                    "message": f"Campaign {campaign_id} not found",
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    video = (
        db.query(YouTubeVideo)
        .filter(YouTubeVideo.video_id == video_id, YouTubeVideo.campaign_id == campaign_id)
        .first()
    )
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": "VIDEO_NOT_FOUND",
                    "message": f"Video {video_id} not found for campaign",
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    preferred_languages = []
    if campaign.primary_language:
        preferred_languages.append(campaign.primary_language.lower())
    data = youtube_service.get_video_transcript(
        video.video_id,
        languages=preferred_languages or None,
        prefer_paid=False,
    )
    return {
        "success": True,
        "data": {
            "video_id": video_id,
            "language": data.get("language"),
            "transcript": data.get("text", ""),
        },
        "message": "Transcript fetched",
        "timestamp": datetime.utcnow().isoformat(),
    }
