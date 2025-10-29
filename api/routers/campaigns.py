"""
Campaign Router - API endpoints for campaign management.
Handles CRUD operations for campaigns.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from api.database import get_db
from api.models import Campaign, CampaignStatus
from api.schemas import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    SuccessResponse
)
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(tags=["campaigns"])


@router.post("/create", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_campaign(
    campaign: CampaignCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new campaign.
    
    Request body should include:
    - name: Campaign name
    - brand_name: Brand/company name
    - brand_url: Brand website URL (optional)
    - product_category: Product/service category
    - campaign_goal: Campaign objective
    - campaign_definition: Detailed campaign description
    - brand_context_text: Brand guidelines and context (optional)
    
    Returns:
        Success response with created campaign data
    """
    try:
        # Create campaign model including neuro-contextual guidance fields
        campaign_data = campaign.model_dump()
        db_campaign = Campaign(
            **campaign_data,
            status=CampaignStatus.DRAFT
        )
        
        # Add to database
        db.add(db_campaign)
        db.commit()
        db.refresh(db_campaign)
        
        logger.info(f"Created campaign: {db_campaign.name} (ID: {db_campaign.id})")
        
        # Convert to response model
        campaign_response = CampaignResponse.model_validate(db_campaign)
        
        return {
            "success": True,
            "data": campaign_response.model_dump(),
            "message": "Campaign created successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "CAMPAIGN_CREATE_ERROR",
                    "message": "Failed to create campaign",
                    "details": str(e)
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/{campaign_id}", response_model=dict)
def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieve a campaign by ID.
    
    Args:
        campaign_id: UUID of the campaign
    
    Returns:
        Success response with campaign data
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": "CAMPAIGN_NOT_FOUND",
                    "message": f"Campaign with id {campaign_id} not found",
                    "details": {}
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    campaign_response = CampaignResponse.model_validate(campaign)
    
    return {
        "success": True,
        "data": campaign_response.model_dump(),
        "message": "Campaign retrieved successfully",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("", response_model=dict)
def list_campaigns(
    skip: int = 0,
    limit: int = 100,
    status_filter: str = None,
    db: Session = Depends(get_db)
):
    """
    List all campaigns with optional filtering.
    
    Query parameters:
        skip: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: 100)
        status: Filter by campaign status (optional)
    
    Returns:
        Success response with list of campaigns
    """
    query = db.query(Campaign)
    
    # Apply status filter if provided
    if status_filter:
        try:
            status_enum = CampaignStatus(status_filter)
            query = query.filter(Campaign.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": {
                        "code": "INVALID_STATUS",
                        "message": f"Invalid status value: {status_filter}",
                        "details": {"valid_statuses": [s.value for s in CampaignStatus]}
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
    
    # Order by created_at descending and apply pagination
    campaigns = query.order_by(Campaign.created_at.desc()).offset(skip).limit(limit).all()
    
    # Convert to response models
    campaigns_response = [CampaignResponse.model_validate(c) for c in campaigns]
    
    return {
        "success": True,
        "data": {
            "campaigns": [c.model_dump() for c in campaigns_response],
            "total": query.count(),
            "skip": skip,
            "limit": limit
        },
        "message": "Campaigns retrieved successfully",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.put("/{campaign_id}/update", response_model=dict)
def update_campaign(
    campaign_id: str,
    campaign_update: CampaignUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an existing campaign.
    
    Args:
        campaign_id: UUID of the campaign
        campaign_update: Fields to update (only provided fields will be updated)
    
    Returns:
        Success response with updated campaign data
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": "CAMPAIGN_NOT_FOUND",
                    "message": f"Campaign with id {campaign_id} not found",
                    "details": {}
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    # Update only provided fields
    update_data = campaign_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(campaign, field, value)
    
    try:
        db.commit()
        db.refresh(campaign)
        logger.info(f"Updated campaign: {campaign.name} (ID: {campaign.id})")
        
        campaign_response = CampaignResponse.model_validate(campaign)
        
        return {
            "success": True,
            "data": campaign_response.model_dump(),
            "message": "Campaign updated successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "CAMPAIGN_UPDATE_ERROR",
                    "message": "Failed to update campaign",
                    "details": str(e)
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.delete("/{campaign_id}", response_model=dict)
def delete_campaign(
    campaign_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a campaign by ID.
    
    Args:
        campaign_id: UUID of the campaign
    
    Returns:
        Success response confirming deletion
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": "CAMPAIGN_NOT_FOUND",
                    "message": f"Campaign with id {campaign_id} not found",
                    "details": {}
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    try:
        campaign_name = campaign.name
        db.delete(campaign)
        db.commit()
        logger.info(f"Deleted campaign: {campaign_name} (ID: {campaign_id})")
        
        return {
            "success": True,
            "data": {"campaign_id": campaign_id},
            "message": "Campaign deleted successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "CAMPAIGN_DELETE_ERROR",
                    "message": "Failed to delete campaign",
                    "details": str(e)
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )
