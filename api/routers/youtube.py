"""
YouTube Router - API endpoints for YouTube video fetching.
Handles video discovery, fetching, and management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import logging

from api.database import get_db
from api.models import YouTubeVideo, Campaign
from api.schemas import YouTubeFetchRequest, YouTubeVideoResponse
from api.services.youtube_service import youtube_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/youtube", tags=["youtube"])


@router.get("/test-connection", response_model=dict)
def test_youtube_connection():
    """
    Test YouTube API connection.
    
    Returns:
        Success response with connection status
    """
    try:
        # Test connection
        is_connected = youtube_service.test_connection()
        
        if is_connected:
            return {
                "success": True,
                "data": {
                    "status": "connected",
                    "api_key_configured": True,
                    "quota_available": True
                },
                "message": "YouTube API connection successful",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise Exception("Connection test failed")
            
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "CONNECTION_ERROR",
                    "message": f"YouTube API connection error: {str(e)}"
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.post("/fetch", response_model=dict)
def fetch_youtube_videos(
    request: YouTubeFetchRequest,
    db: Session = Depends(get_db)
):
    """
    Fetch YouTube videos for a campaign using its keywords.
    
    Request body:
    - campaign_id: UUID of the campaign
    - max_results: Maximum videos per keyword (1-200, default: 50)
    - language: Language code (default: "en")
    - region: Region code (default: "US")
    - published_after: Optional datetime filter
    - published_before: Optional datetime filter
    - order: Sort order (relevance, date, rating, viewCount, title)
    - video_duration: Duration filter (any, short, medium, long)
    - video_definition: Definition filter (any, standard, high)
    
    Returns:
        Success response with fetched videos
    """
    try:
        # Verify campaign exists
        campaign = db.query(Campaign).filter(Campaign.id == request.campaign_id).first()
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": {
                        "code": "CAMPAIGN_NOT_FOUND",
                        "message": f"Campaign with id {request.campaign_id} not found"
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        # Fetch videos using YouTube service
        language = request.language or campaign.primary_language or "en"
        region = request.region or campaign.primary_market or "US"

        fetch_result = youtube_service.fetch_videos_for_campaign(
            db=db,
            campaign_id=request.campaign_id,
            max_results=request.max_results,
            language=language,
            region=region,
            published_after=request.published_after,
            published_before=request.published_before,
            order=request.order,
            video_duration=request.video_duration,
            video_definition=request.video_definition
        )
        
        # Convert to response models
        videos = fetch_result.get('videos', [])
        videos_response = [YouTubeVideoResponse.model_validate(v) for v in videos]
        
        logger.info(f"Fetched {fetch_result.get('new_videos', len(videos))} videos for campaign {request.campaign_id}")
        
        return {
            "success": True,
            "data": {
                "campaign_id": request.campaign_id,
                "new_videos": fetch_result.get('new_videos', len(videos)),
                "duplicate_videos": fetch_result.get('duplicate_videos', 0),
                "total_videos": fetch_result.get('total_videos', len(videos)),
                "videos": [v.model_dump() for v in videos_response],
                "quota_used": fetch_result.get('quota_used', youtube_service.quota_used)
            },
            "message": f"Successfully fetched {len(videos)} videos",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(e)
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Failed to fetch videos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "FETCH_ERROR",
                    "message": f"Failed to fetch videos: {str(e)}"
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/videos/{campaign_id}", response_model=dict)
def get_campaign_videos(
    campaign_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get all videos for a campaign.
    
    Args:
        campaign_id: Campaign UUID
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
    
    Returns:
        Success response with list of videos
    """
    try:
        # Get videos from database
        videos = db.query(YouTubeVideo).filter(
            YouTubeVideo.campaign_id == campaign_id
        ).order_by(
            YouTubeVideo.view_count.desc()
        ).offset(skip).limit(limit).all()
        
        # Get total count
        total_count = db.query(YouTubeVideo).filter(
            YouTubeVideo.campaign_id == campaign_id
        ).count()
        
        # Convert to response models
        videos_response = [YouTubeVideoResponse.model_validate(v) for v in videos]
        
        return {
            "success": True,
            "data": {
                "campaign_id": campaign_id,
                "total_videos": total_count,
                "returned_videos": len(videos),
                "skip": skip,
                "limit": limit,
                "videos": [v.model_dump() for v in videos_response]
            },
            "message": f"Retrieved {len(videos)} videos",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to retrieve videos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "RETRIEVAL_ERROR",
                    "message": f"Failed to retrieve videos: {str(e)}"
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/stats/{campaign_id}", response_model=dict)
def get_campaign_video_stats(
    campaign_id: str,
    db: Session = Depends(get_db)
):
    """
    Get aggregate statistics for a campaign's videos.
    """
    try:
        stats = youtube_service.get_campaign_video_stats(db=db, campaign_id=campaign_id)
        
        return {
            "success": True,
            "data": stats,
            "message": "Video statistics retrieved successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to retrieve video stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "STATS_ERROR",
                    "message": f"Failed to retrieve video statistics: {str(e)}"
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/video/{video_id}", response_model=dict)
def get_video_details(
    video_id: str,
    db: Session = Depends(get_db)
):
    """
    Get details for a specific video by YouTube video ID.
    
    Args:
        video_id: YouTube video ID (not database ID)
    
    Returns:
        Success response with video details
    """
    try:
        video = db.query(YouTubeVideo).filter(
            YouTubeVideo.video_id == video_id
        ).first()
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": {
                        "code": "VIDEO_NOT_FOUND",
                        "message": f"Video with id {video_id} not found"
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        video_response = YouTubeVideoResponse.model_validate(video)
        
        return {
            "success": True,
            "data": video_response.model_dump(),
            "message": "Video details retrieved successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve video details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "RETRIEVAL_ERROR",
                    "message": f"Failed to retrieve video: {str(e)}"
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.delete("/videos/{campaign_id}", response_model=dict)
def delete_campaign_videos(
    campaign_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete all videos for a campaign.
    
    Args:
        campaign_id: Campaign UUID
    
    Returns:
        Success response with deletion count
    """
    try:
        # Get count before deletion
        video_count = db.query(YouTubeVideo).filter(
            YouTubeVideo.campaign_id == campaign_id
        ).count()
        
        # Delete videos
        db.query(YouTubeVideo).filter(
            YouTubeVideo.campaign_id == campaign_id
        ).delete()
        
        db.commit()
        
        logger.info(f"Deleted {video_count} videos for campaign {campaign_id}")
        
        return {
            "success": True,
            "data": {
                "campaign_id": campaign_id,
                "deleted_count": video_count
            },
            "message": f"Successfully deleted {video_count} videos",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete videos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "DELETE_ERROR",
                    "message": f"Failed to delete videos: {str(e)}"
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )
