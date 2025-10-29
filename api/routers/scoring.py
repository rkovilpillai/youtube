"""
Scoring Router - Phase 3 endpoints for Liz AI contextual scoring.
Provides NLP analysis, brand safety classification, contextual scoring,
and batch utilities for campaign videos.
"""
from datetime import datetime
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Campaign, YouTubeVideo, VideoScore
from api.schemas import (
    BatchVideoScoringRequest,
    VideoScoringRequest,
)
from api.services.scoring_engine import scoring_engine


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scoring", tags=["scoring"])


def _get_campaign(db: Session, campaign_id: str) -> Campaign:
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": "CAMPAIGN_NOT_FOUND",
                    "message": f"Campaign with id {campaign_id} not found",
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
    return campaign


def _get_video(db: Session, campaign_id: str, video_id: str) -> YouTubeVideo:
    video = (
        db.query(YouTubeVideo)
        .filter(
            YouTubeVideo.video_id == video_id,
            YouTubeVideo.campaign_id == campaign_id,
        )
        .first()
    )
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": "VIDEO_NOT_FOUND",
                    "message": f"Video {video_id} not found for campaign {campaign_id}",
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
    return video


def _serialize_score(video: YouTubeVideo, score: VideoScore) -> dict:
    """Convert ORM objects into API payload."""
    return {
        "id": score.id,
        "campaign_id": score.campaign_id,
        "video_record_id": score.video_id,
        "video_id": video.video_id,
        "channel_id": video.channel_id,
        "video_url": f"https://www.youtube.com/watch?v={video.video_id}",
        "channel_url": f"https://www.youtube.com/channel/{video.channel_id}",
        "semantic_similarity_score": score.semantic_similarity_score,
        "intent_score": score.intent_score,
        "interest_score": score.interest_score,
        "emotion_score": score.emotion_score,
        "intent_type": score.intent_type,
        "interest_topics": score.interest_topics or [],
        "emotion_type": score.emotion_type,
        "contextual_score": score.contextual_score,
        "brand_safety_status": score.brand_safety_status.value,
        "brand_suitability": score.brand_suitability.value,
        "sentiment": score.sentiment.value,
        "tone": score.tone,
        "key_entities": score.key_entities or [],
        "key_topics": score.key_topics or [],
        "targeting_recommendation": score.targeting_recommendation.value,
        "suggested_bid_modifier": score.suggested_bid_modifier,
        "reasoning": score.reasoning,
        "scored_at": score.scored_at.isoformat(),
    }


@router.post("/nlp", response_model=dict)
def analyze_video_nlp(request: VideoScoringRequest, db: Session = Depends(get_db)):
    """Return NLP dimension scores without persisting."""
    campaign = _get_campaign(db, request.campaign_id)
    video = _get_video(db, request.campaign_id, request.video_id)
    nlp_scores = scoring_engine.analyze_nlp(campaign, video)
    logger.info(
        "Computed NLP scores for campaign %s video %s", campaign.id, video.video_id
    )
    return {
        "success": True,
        "data": nlp_scores,
        "message": "NLP scores generated successfully",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/brand-safety", response_model=dict)
def analyze_brand_safety(request: VideoScoringRequest, db: Session = Depends(get_db)):
    """Return brand safety classification."""
    campaign = _get_campaign(db, request.campaign_id)
    video = _get_video(db, request.campaign_id, request.video_id)
    nlp_scores = scoring_engine.analyze_nlp(campaign, video)
    brand = scoring_engine.evaluate_brand_safety(video, nlp_scores["sentiment"])
    logger.info(
        "Computed brand safety for campaign %s video %s",
        campaign.id,
        video.video_id,
    )
    return {
        "success": True,
        "data": brand,
        "message": "Brand safety analysis complete",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/contextual-score", response_model=dict)
def score_video(request: VideoScoringRequest, db: Session = Depends(get_db)):
    """Run full contextual scoring workflow and persist results."""
    campaign = _get_campaign(db, request.campaign_id)
    video = _get_video(db, request.campaign_id, request.video_id)
    score = scoring_engine.score_video(
        db=db,
        campaign=campaign,
        video=video,
        use_transcript=request.use_transcript,
    )
    logger.info(
        "Contextual score %.2f saved for video %s",
        score.contextual_score,
        video.video_id,
    )
    return {
        "success": True,
        "data": _serialize_score(video, score),
        "message": "Video scored successfully",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/batch", response_model=dict)
def batch_score_videos(request: BatchVideoScoringRequest, db: Session = Depends(get_db)):
    """Score multiple videos sequentially."""
    campaign = _get_campaign(db, request.campaign_id)
    results: List[dict] = []
    errors: List[dict] = []

    for video_id in request.video_ids:
        try:
            video = _get_video(db, request.campaign_id, video_id)
            score = scoring_engine.score_video(
                db=db,
                campaign=campaign,
                video=video,
                use_transcript=request.use_transcript,
            )
            results.append(
                {
                    "video_id": video_id,
                    "contextual_score": score.contextual_score,
                    "brand_suitability": score.brand_suitability.value,
                }
            )
        except HTTPException as exc:
            errors.append(
                {
                    "video_id": video_id,
                    "error": exc.detail if isinstance(exc.detail, dict) else str(exc),
                }
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed to score video %s: %s", video_id, exc)
            errors.append({"video_id": video_id, "error": str(exc)})

    message = f"Scored {len(results)} videos"
    if errors:
        message += f", {len(errors)} failures"

    return {
        "success": True,
        "data": {
            "campaign_id": request.campaign_id,
            "processed": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
        },
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/video/{video_id}", response_model=dict)
def get_video_score(video_id: str, db: Session = Depends(get_db)):
    """Retrieve stored score for a single video."""
    video = db.query(YouTubeVideo).filter(YouTubeVideo.video_id == video_id).first()
    if not video or not video.score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": "SCORE_NOT_FOUND",
                    "message": f"No score found for video {video_id}",
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    return {
        "success": True,
        "data": _serialize_score(video, video.score),
        "message": "Video score retrieved successfully",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/campaign/{campaign_id}", response_model=dict)
def get_campaign_scores(campaign_id: str, db: Session = Depends(get_db)):
    """Return all scored videos for a campaign with summary metrics."""
    scores = (
        db.query(VideoScore)
        .filter(VideoScore.campaign_id == campaign_id)
        .join(YouTubeVideo)
        .all()
    )
    if not scores:
        return {
            "success": True,
            "data": {
                "campaign_id": campaign_id,
                "total_scored": 0,
                "average_contextual_score": 0,
                "scores": [],
            },
            "message": "No scores found for campaign",
            "timestamp": datetime.utcnow().isoformat(),
        }

    serialized = [_serialize_score(score.video, score) for score in scores]
    avg_score = sum(item["contextual_score"] for item in serialized) / len(serialized)

    recommendation_counts = {}
    for item in serialized:
        rec = item["targeting_recommendation"]
        recommendation_counts[rec] = recommendation_counts.get(rec, 0) + 1

    return {
        "success": True,
        "data": {
            "campaign_id": campaign_id,
            "total_scored": len(serialized),
            "average_contextual_score": round(avg_score, 3),
            "recommendation_breakdown": recommendation_counts,
            "scores": serialized,
        },
        "message": f"Retrieved {len(serialized)} scored videos",
        "timestamp": datetime.utcnow().isoformat(),
    }
