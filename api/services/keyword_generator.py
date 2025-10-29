"""
Keyword Generator Service - Business logic for keyword generation and management.
Orchestrates AI service calls and database operations.
"""
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import logging

from api.models import Campaign, Keyword, KeywordType, KeywordSource, KeywordStatus
from api.services.liz_ai import liz_ai_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KeywordGeneratorService:
    """
    Service for generating and managing keywords for campaigns.
    Handles AI integration and database persistence.
    """
    
    def generate_keywords_for_campaign(
        self,
        db: Session,
        campaign_id: str,
        num_core: int = 10,
        num_long_tail: int = 15,
        num_related: int = 10,
        num_intent_based: int = 10
    ) -> Dict[str, Any]:
        """
        Generate keywords for a campaign using Liz AI and save to database.
        
        Args:
            db: Database session
            campaign_id: UUID of the campaign
            num_core: Number of core keywords to generate
            num_long_tail: Number of long-tail keywords to generate
            num_related: Number of related keywords to generate
            num_intent_based: Number of intent-based keywords to generate
        
        Returns:
            Dictionary containing:
                - campaign_id: Campaign UUID
                - total_keywords: Total number of keywords generated
                - keywords_by_type: Count of keywords by type
                - keywords: List of keyword objects
        
        Raises:
            ValueError: If campaign not found
            Exception: If keyword generation fails
        """
        # Fetch campaign
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise ValueError(f"Campaign with id {campaign_id} not found")
        
        logger.info(f"Starting keyword generation for campaign: {campaign.name}")
        
        # Prepare campaign data for AI
        primary_language = campaign.primary_language or "en"
        primary_market = campaign.primary_market or "US"

        campaign_data = {
            "name": campaign.name,
            "brand_name": campaign.brand_name,
            "product_category": campaign.product_category,
            "campaign_goal": campaign.campaign_goal,
            "campaign_definition": campaign.campaign_definition,
            "brand_context_text": campaign.brand_context_text or "",
            "primary_language": primary_language,
            "primary_market": primary_market,
        }

        # Generate keywords using Liz AI
        try:
            keywords_data = liz_ai_service.generate_keywords(
                campaign_data=campaign_data,
                num_core=num_core,
                num_long_tail=num_long_tail,
                num_related=num_related,
                num_intent_based=num_intent_based
            )
        except Exception as e:
            logger.error(f"Failed to generate keywords: {e}")
            raise Exception(f"Keyword generation failed: {str(e)}")
        
        # Map AI response to database models
        keyword_type_mapping = {
            "core_keywords": KeywordType.CORE,
            "long_tail_keywords": KeywordType.LONG_TAIL,
            "related_topics": KeywordType.RELATED,
            "intent_based_keywords": KeywordType.INTENT_BASED
        }
        
        created_keywords = []
        keywords_by_type = {}
        
        # Process each keyword category
        for category, keyword_type in keyword_type_mapping.items():
            keywords_list = keywords_data.get(category, [])
            keywords_by_type[keyword_type.value] = len(keywords_list)
            
            for kw_data in keywords_list:
                keyword = Keyword(
                    campaign_id=campaign_id,
                    keyword=kw_data["keyword"],
                    keyword_type=keyword_type,
                    relevance_score=kw_data["relevance_score"],
                    source=KeywordSource.AI_GENERATED,
                    status=KeywordStatus.ACTIVE
                )
                db.add(keyword)
                created_keywords.append(keyword)
        
        # Commit to database
        try:
            db.commit()
            logger.info(f"Successfully saved {len(created_keywords)} keywords to database")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save keywords to database: {e}")
            raise Exception(f"Database error: {str(e)}")
        
        # Refresh objects to get IDs
        for keyword in created_keywords:
            db.refresh(keyword)
        
        return {
            "campaign_id": campaign_id,
            "total_keywords": len(created_keywords),
            "keywords_by_type": keywords_by_type,
            "keywords": created_keywords
        }
    
    def get_campaign_keywords(
        self,
        db: Session,
        campaign_id: str,
        keyword_type: str = None,
        status: str = None
    ) -> List[Keyword]:
        """
        Retrieve keywords for a campaign with optional filtering.
        
        Args:
            db: Database session
            campaign_id: UUID of the campaign
            keyword_type: Optional filter by keyword type
            status: Optional filter by status
        
        Returns:
            List of Keyword objects
        """
        query = db.query(Keyword).filter(Keyword.campaign_id == campaign_id)
        
        if keyword_type:
            query = query.filter(Keyword.keyword_type == keyword_type)
        
        if status:
            query = query.filter(Keyword.status == status)
        
        # Order by relevance score descending, then by created_at
        query = query.order_by(Keyword.relevance_score.desc(), Keyword.created_at.desc())
        
        return query.all()
    
    def add_manual_keyword(
        self,
        db: Session,
        campaign_id: str,
        keyword_text: str,
        keyword_type: KeywordType,
        relevance_score: float
    ) -> Keyword:
        """
        Add a keyword manually (not AI-generated).
        
        Args:
            db: Database session
            campaign_id: UUID of the campaign
            keyword_text: The keyword text
            keyword_type: Type of keyword
            relevance_score: Relevance score (0-1)
        
        Returns:
            Created Keyword object
        
        Raises:
            ValueError: If campaign not found or validation fails
        """
        # Validate campaign exists
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise ValueError(f"Campaign with id {campaign_id} not found")
        
        # Validate relevance score
        if not 0.0 <= relevance_score <= 1.0:
            raise ValueError("Relevance score must be between 0.0 and 1.0")
        
        # Create keyword
        keyword = Keyword(
            campaign_id=campaign_id,
            keyword=keyword_text.strip(),
            keyword_type=keyword_type,
            relevance_score=relevance_score,
            source=KeywordSource.MANUAL,
            status=KeywordStatus.ACTIVE
        )
        
        db.add(keyword)
        
        try:
            db.commit()
            db.refresh(keyword)
            logger.info(f"Manually added keyword: {keyword_text}")
            return keyword
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to add manual keyword: {e}")
            raise Exception(f"Database error: {str(e)}")
    
    def delete_keyword(self, db: Session, keyword_id: str) -> bool:
        """
        Delete a keyword by ID.
        
        Args:
            db: Database session
            keyword_id: UUID of the keyword
        
        Returns:
            True if deleted, False if not found
        """
        keyword = db.query(Keyword).filter(Keyword.id == keyword_id).first()
        if not keyword:
            return False
        
        db.delete(keyword)
        db.commit()
        logger.info(f"Deleted keyword: {keyword.keyword}")
        return True
    
    def update_keyword_status(
        self,
        db: Session,
        keyword_id: str,
        status: KeywordStatus
    ) -> Keyword:
        """
        Update the status of a keyword.
        
        Args:
            db: Database session
            keyword_id: UUID of the keyword
            status: New status
        
        Returns:
            Updated Keyword object
        
        Raises:
            ValueError: If keyword not found
        """
        keyword = db.query(Keyword).filter(Keyword.id == keyword_id).first()
        if not keyword:
            raise ValueError(f"Keyword with id {keyword_id} not found")
        
        keyword.status = status
        db.commit()
        db.refresh(keyword)
        logger.info(f"Updated keyword {keyword.keyword} status to {status.value}")
        return keyword


# Global instance
keyword_generator_service = KeywordGeneratorService()
