"""
Keywords Router - API endpoints for keyword generation and management.
Handles keyword CRUD operations and AI-powered generation.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from api.database import get_db
from api.models import KeywordType, KeywordSource
from api.schemas import (
    KeywordCreate,
    KeywordResponse,
    KeywordGenerateRequest,
    KeywordGenerateResponse
)
from api.services.keyword_generator import keyword_generator_service
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/keywords", tags=["keywords"])


@router.post("/generate", response_model=dict)
def generate_keywords(
    request: KeywordGenerateRequest,
    db: Session = Depends(get_db)
):
    """
    Generate keywords for a campaign using Liz AI.
    
    This endpoint:
    1. Retrieves the campaign details
    2. Calls Liz AI (OpenAI GPT-4o) to generate keywords in 4 categories
    3. Saves all keywords to the database
    4. Returns the generated keywords
    
    Request body:
    - campaign_id: UUID of the campaign
    - num_core_keywords: Number of core keywords (5-20, default: 10)
    - num_long_tail: Number of long-tail keywords (10-30, default: 15)
    - num_related: Number of related keywords (5-20, default: 10)
    - num_intent_based: Number of intent-based keywords (5-20, default: 10)
    
    Returns:
        Success response with generated keywords grouped by type
    """
    try:
        # Generate keywords using service
        result = keyword_generator_service.generate_keywords_for_campaign(
            db=db,
            campaign_id=request.campaign_id,
            num_core=request.num_core_keywords,
            num_long_tail=request.num_long_tail,
            num_related=request.num_related,
            num_intent_based=request.num_intent_based
        )
        
        # Convert keywords to response models
        keywords_response = [KeywordResponse.model_validate(kw) for kw in result["keywords"]]
        
        return {
            "success": True,
            "data": {
                "campaign_id": result["campaign_id"],
                "total_keywords": result["total_keywords"],
                "keywords_by_type": result["keywords_by_type"],
                "keywords": [kw.model_dump() for kw in keywords_response]
            },
            "message": f"Successfully generated {result['total_keywords']} keywords",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": "CAMPAIGN_NOT_FOUND",
                    "message": str(e),
                    "details": {}
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Failed to generate keywords: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "KEYWORD_GENERATION_ERROR",
                    "message": "Failed to generate keywords",
                    "details": str(e)
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/{campaign_id}", response_model=dict)
def get_campaign_keywords(
    campaign_id: str,
    keyword_type: str = None,
    status_filter: str = None,
    db: Session = Depends(get_db)
):
    """
    Retrieve all keywords for a campaign with optional filtering.
    
    Args:
        campaign_id: UUID of the campaign
        keyword_type: Optional filter by type (core, long-tail, related, intent-based)
        status: Optional filter by status (active, inactive)
    
    Returns:
        Success response with list of keywords
    """
    try:
        keywords = keyword_generator_service.get_campaign_keywords(
            db=db,
            campaign_id=campaign_id,
            keyword_type=keyword_type,
            status=status_filter
        )
        
        # Convert to response models
        keywords_response = [KeywordResponse.model_validate(kw) for kw in keywords]
        
        # Group by type for summary
        keywords_by_type = {}
        for kw in keywords:
            type_key = kw.keyword_type.value
            keywords_by_type[type_key] = keywords_by_type.get(type_key, 0) + 1
        
        return {
            "success": True,
            "data": {
                "campaign_id": campaign_id,
                "total_keywords": len(keywords),
                "keywords_by_type": keywords_by_type,
                "keywords": [kw.model_dump() for kw in keywords_response]
            },
            "message": "Keywords retrieved successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to retrieve keywords: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "KEYWORD_RETRIEVAL_ERROR",
                    "message": "Failed to retrieve keywords",
                    "details": str(e)
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.post("/manual-add", response_model=dict, status_code=status.HTTP_201_CREATED)
def add_manual_keyword(
    keyword: KeywordCreate,
    db: Session = Depends(get_db)
):
    """
    Add a keyword manually (not AI-generated).
    
    Request body:
    - campaign_id: UUID of the campaign
    - keyword: Keyword text
    - keyword_type: Type (core, long-tail, related, intent-based)
    - relevance_score: Score between 0.0 and 1.0
    - source: Source (defaults to 'manual')
    
    Returns:
        Success response with created keyword
    """
    try:
        # Add keyword using service
        db_keyword = keyword_generator_service.add_manual_keyword(
            db=db,
            campaign_id=keyword.campaign_id,
            keyword_text=keyword.keyword,
            keyword_type=KeywordType(keyword.keyword_type.value),
            relevance_score=keyword.relevance_score
        )
        
        keyword_response = KeywordResponse.model_validate(db_keyword)
        
        return {
            "success": True,
            "data": keyword_response.model_dump(),
            "message": "Keyword added successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(e),
                    "details": {}
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Failed to add keyword: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "KEYWORD_ADD_ERROR",
                    "message": "Failed to add keyword",
                    "details": str(e)
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.delete("/{keyword_id}", response_model=dict)
def delete_keyword(
    keyword_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a keyword by ID.
    
    Args:
        keyword_id: UUID of the keyword
    
    Returns:
        Success response confirming deletion
    """
    try:
        deleted = keyword_generator_service.delete_keyword(db=db, keyword_id=keyword_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": {
                        "code": "KEYWORD_NOT_FOUND",
                        "message": f"Keyword with id {keyword_id} not found",
                        "details": {}
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        return {
            "success": True,
            "data": {"keyword_id": keyword_id},
            "message": "Keyword deleted successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete keyword: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "KEYWORD_DELETE_ERROR",
                    "message": "Failed to delete keyword",
                    "details": str(e)
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )
