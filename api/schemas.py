"""
Pydantic schemas for request/response validation.
Provides type safety and automatic API documentation.
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from datetime import datetime
from enum import Enum


# Enums
class CampaignStatusEnum(str, Enum):
    """Campaign status enumeration."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class KeywordTypeEnum(str, Enum):
    """Keyword type enumeration."""
    CORE = "core"
    LONG_TAIL = "long-tail"
    RELATED = "related"
    INTENT_BASED = "intent-based"


class KeywordSourceEnum(str, Enum):
    """Keyword source enumeration."""
    AI_GENERATED = "ai-generated"
    MANUAL = "manual"


class KeywordStatusEnum(str, Enum):
    """Keyword status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"


class BrandSafetyStatusEnum(str, Enum):
    """Brand safety classification."""
    SAFE = "safe"
    REVIEW = "review"
    UNSAFE = "unsafe"


class BrandSuitabilityEnum(str, Enum):
    """Brand suitability tiers."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SentimentEnum(str, Enum):
    """Sentiment polarity."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class TargetingRecommendationEnum(str, Enum):
    """Targeting recommendations."""
    STRONG_MATCH = "strong_match"
    MODERATE_MATCH = "moderate_match"
    WEAK_MATCH = "weak_match"
    AVOID = "avoid"


# Campaign Schemas
class CampaignCreate(BaseModel):
    """Schema for creating a new campaign."""
    name: str = Field(..., min_length=1, max_length=255, description="Campaign name")
    brand_name: str = Field(..., min_length=1, max_length=255, description="Brand/company name")
    brand_url: Optional[str] = Field(None, description="Brand website URL")
    product_category: str = Field(..., min_length=1, max_length=255, description="Product/service category")
    campaign_goal: str = Field(..., min_length=1, max_length=255, description="Campaign objective")
    campaign_definition: str = Field(..., min_length=1, max_length=5000, description="Detailed campaign description")
    brand_context_text: Optional[str] = Field(None, max_length=10000, description="Brand guidelines and context")
    audience_intent: Optional[str] = Field(None, description="Primary campaign intent for neuro-guidance")
    audience_persona: Optional[str] = Field(None, description="Primary audience persona")
    tone_profile: Optional[str] = Field(None, description="Dominant tone guidance")
    emotion_guidance: Optional[List[str]] = Field(None, description="Desired emotional signals")
    interest_guidance: Optional[List[str]] = Field(None, description="Topic clusters to emphasize")
    guardrail_terms: Optional[List[str]] = Field(None, description="Keywords or themes to avoid")
    inspiration_links: Optional[List[str]] = Field(None, description="Reference links or mood board inspirations")
    primary_language: Optional[str] = Field(None, description="Primary language (ISO 639-1)")
    primary_market: Optional[str] = Field(None, description="Primary market/country (ISO 3166-1 alpha-2)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Summer Tech Launch Campaign",
                "brand_name": "TechCo",
                "brand_url": "https://www.techco.com",
                "product_category": "Consumer Electronics",
                "campaign_goal": "Product awareness and consideration",
                "campaign_definition": "Launch campaign for our new smartphone targeting tech enthusiasts aged 25-40",
                "brand_context_text": "Brand values: Innovation, Quality, Sustainability. Tone: Professional yet approachable."
            }
        }


class CampaignUpdate(BaseModel):
    """Schema for updating an existing campaign."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    brand_name: Optional[str] = Field(None, min_length=1, max_length=255)
    brand_url: Optional[str] = None
    product_category: Optional[str] = Field(None, min_length=1, max_length=255)
    campaign_goal: Optional[str] = Field(None, min_length=1, max_length=255)
    campaign_definition: Optional[str] = Field(None, min_length=1, max_length=5000)
    brand_context_text: Optional[str] = Field(None, max_length=10000)
    status: Optional[CampaignStatusEnum] = None
    audience_intent: Optional[str] = None
    audience_persona: Optional[str] = None
    tone_profile: Optional[str] = None
    emotion_guidance: Optional[List[str]] = None
    interest_guidance: Optional[List[str]] = None
    guardrail_terms: Optional[List[str]] = None
    inspiration_links: Optional[List[str]] = None
    primary_language: Optional[str] = None
    primary_market: Optional[str] = None


class CampaignResponse(BaseModel):
    """Schema for campaign response."""
    id: str
    name: str
    brand_name: str
    brand_url: Optional[str]
    product_category: str
    campaign_goal: str
    campaign_definition: str
    brand_context_text: Optional[str]
    status: CampaignStatusEnum
    created_at: datetime
    updated_at: datetime
    audience_intent: Optional[str]
    audience_persona: Optional[str]
    tone_profile: Optional[str]
    emotion_guidance: Optional[List[str]]
    interest_guidance: Optional[List[str]]
    guardrail_terms: Optional[List[str]]
    inspiration_links: Optional[List[str]]
    primary_language: Optional[str]
    primary_market: Optional[str]
    
    class Config:
        from_attributes = True


# Keyword Schemas
class KeywordCreate(BaseModel):
    """Schema for creating a keyword manually."""
    campaign_id: str = Field(..., description="Campaign UUID")
    keyword: str = Field(..., min_length=1, max_length=255, description="Keyword text")
    keyword_type: KeywordTypeEnum = Field(..., description="Type of keyword")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Relevance score (0-1)")
    source: KeywordSourceEnum = Field(default=KeywordSourceEnum.MANUAL, description="Keyword source")
    
    class Config:
        json_schema_extra = {
            "example": {
                "campaign_id": "123e4567-e89b-12d3-a456-426614174000",
                "keyword": "smartphone reviews",
                "keyword_type": "core",
                "relevance_score": 0.95,
                "source": "manual"
            }
        }


class KeywordResponse(BaseModel):
    """Schema for keyword response."""
    id: str
    campaign_id: str
    keyword: str
    keyword_type: KeywordTypeEnum
    relevance_score: float
    source: KeywordSourceEnum
    status: KeywordStatusEnum
    created_at: datetime
    
    class Config:
        from_attributes = True


class KeywordGenerateRequest(BaseModel):
    """Schema for keyword generation request."""
    campaign_id: str = Field(..., description="Campaign UUID to generate keywords for")
    num_core_keywords: int = Field(default=10, ge=5, le=20, description="Number of core keywords to generate")
    num_long_tail: int = Field(default=15, ge=10, le=30, description="Number of long-tail keywords to generate")
    num_related: int = Field(default=10, ge=5, le=20, description="Number of related topic keywords to generate")
    num_intent_based: int = Field(default=10, ge=5, le=20, description="Number of intent-based keywords to generate")
    
    class Config:
        json_schema_extra = {
            "example": {
                "campaign_id": "123e4567-e89b-12d3-a456-426614174000",
                "num_core_keywords": 10,
                "num_long_tail": 15,
                "num_related": 10,
                "num_intent_based": 10
            }
        }


class KeywordGenerateResponse(BaseModel):
    """Schema for keyword generation response."""
    campaign_id: str
    total_keywords: int
    keywords_by_type: dict
    keywords: List[KeywordResponse]


# API Standard Response Schemas
class SuccessResponse(BaseModel):
    """Standard success response wrapper."""
    success: bool = True
    data: dict
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Standard error response wrapper."""
    success: bool = False
    error: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid input data",
                    "details": {"field": "campaign_name", "issue": "Field is required"}
                },
                "timestamp": "2025-01-15T10:30:00Z"
            }
        }


# YouTube Schemas
class YouTubeFetchRequest(BaseModel):
    """Schema for YouTube video fetch request."""
    campaign_id: str = Field(..., description="Campaign UUID")
    max_results: int = Field(default=50, ge=1, le=200, description="Maximum videos per keyword")
    language: str = Field(default="en", description="Language code (e.g., en, es, fr)")
    region: str = Field(default="US", description="Region code (e.g., US, UK, IN)")
    published_after: Optional[datetime] = Field(None, description="Filter videos published after this date")
    published_before: Optional[datetime] = Field(None, description="Filter videos published before this date")
    order: str = Field(default="relevance", description="Sort order: relevance, date, rating, viewCount, title")
    video_duration: Optional[str] = Field(None, description="Duration filter: any, short, medium, long")
    video_definition: Optional[str] = Field(None, description="Definition filter: any, standard, high")
    include_channels: bool = Field(default=True, description="Whether to fetch channels alongside videos")
    channel_max_results: Optional[int] = Field(
        default=25,
        ge=1,
        le=100,
        description="Maximum channels per keyword rotation when include_channels is true"
    )
    channel_order: Optional[str] = Field(
        default=None,
        description="Sort order for channel discovery (defaults to the video order value when omitted)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "campaign_id": "123e4567-e89b-12d3-a456-426614174000",
                "max_results": 50,
                "language": "en",
                "region": "US",
                "order": "relevance",
                "include_channels": True,
                "channel_max_results": 25
            }
        }


class YouTubeChannelFetchRequest(BaseModel):
    """Schema for YouTube channel fetch request."""
    campaign_id: str = Field(..., description="Campaign UUID")
    max_results: int = Field(default=25, ge=1, le=100, description="Maximum channels per keyword rotation")
    language: str = Field(default="en", description="Language code for relevance weighting")
    region: str = Field(default="US", description="Region code influencing search results")
    order: str = Field(default="relevance", description="Sort order: relevance, date, rating, viewCount")

    class Config:
        json_schema_extra = {
            "example": {
                "campaign_id": "123e4567-e89b-12d3-a456-426614174000",
                "max_results": 25,
                "language": "en",
                "region": "US",
                "order": "relevance"
            }
        }


class YouTubeVideoResponse(BaseModel):
    """Schema for YouTube video response."""
    id: str
    campaign_id: str
    video_id: str
    channel_id: str
    title: str
    description: Optional[str]
    channel_title: Optional[str]
    tags: Optional[List[str]]
    category: Optional[str]
    duration: Optional[str]
    published_at: Optional[datetime]
    view_count: int
    like_count: int
    comment_count: int
    channel_view_count: Optional[int]
    channel_subscriber_count: Optional[int]
    thumbnail_url: Optional[str]
    fetched_at: datetime
    
    class Config:
        from_attributes = True


class YouTubeChannelResponse(BaseModel):
    """Schema for YouTube channel response."""
    id: str
    campaign_id: str
    channel_id: str
    title: str
    description: Optional[str]
    custom_url: Optional[str]
    country: Optional[str]
    published_at: Optional[datetime]
    thumbnail_url: Optional[str]
    keywords: Optional[List[str]]
    topic_categories: Optional[List[str]]
    subscriber_count: Optional[int]
    view_count: Optional[int]
    video_count: Optional[int]
    fetched_at: datetime

    class Config:
        from_attributes = True


# Scoring Schemas
class VideoScoringRequest(BaseModel):
    """Request body for scoring a single video."""
    campaign_id: str = Field(..., description="Campaign UUID")
    video_id: str = Field(..., description="YouTube video ID")
    use_transcript: bool = Field(default=False, description="Whether to include transcript when scoring")
    
    class Config:
        json_schema_extra = {
            "example": {
                "campaign_id": "123e4567-e89b-12d3-a456-426614174000",
                "video_id": "dQw4w9WgXcQ",
                "use_transcript": False
            }
        }


class BatchVideoScoringRequest(BaseModel):
    """Request body for scoring multiple videos."""
    campaign_id: str = Field(..., description="Campaign UUID")
    video_ids: List[str] = Field(..., min_length=1, description="List of YouTube video IDs")
    use_transcript: bool = Field(default=False, description="Whether to include transcripts when scoring")


class NLPScoringResponse(BaseModel):
    """NLP dimension scores."""
    semantic_similarity_score: float
    intent_score: float
    interest_score: float
    emotion_score: float
    sentiment: SentimentEnum
    tone: str
    key_entities: List[str]
    key_topics: List[str]


class BrandSafetyResponse(BaseModel):
    """Brand safety response."""
    brand_safety_status: BrandSafetyStatusEnum


class VideoScoreResponse(BaseModel):
    """Full contextual score response."""
    id: str
    campaign_id: str
    video_record_id: str = Field(..., description="Internal UUID for youtube_videos table")
    video_id: str = Field(..., description="Public YouTube video ID")
    semantic_similarity_score: float
    intent_score: float
    interest_score: float
    emotion_score: float
    intent_type: Optional[str]
    interest_topics: Optional[List[str]]
    emotion_type: Optional[str]
    contextual_score: float
    brand_safety_status: BrandSafetyStatusEnum
    brand_suitability: BrandSuitabilityEnum
    sentiment: SentimentEnum
    tone: str
    key_entities: List[str]
    key_topics: List[str]
    targeting_recommendation: TargetingRecommendationEnum
    suggested_bid_modifier: float
    reasoning: Optional[str]
    scored_at: datetime
