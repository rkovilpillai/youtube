"""
SQLAlchemy database models for YouTube Contextual Product Pipeline.
Follows exact schema specifications from PROJECT_KNOWLEDGE_BASE.md.
"""
from typing import Optional
from sqlalchemy import Column, String, Text, Float, Enum, ForeignKey, DateTime, Integer, JSON, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from api.database import Base


# Enums
class CampaignStatus(str, enum.Enum):
    """Campaign status enumeration."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class KeywordType(str, enum.Enum):
    """Keyword type enumeration."""
    CORE = "core"
    LONG_TAIL = "long-tail"
    RELATED = "related"
    INTENT_BASED = "intent-based"


class KeywordStatus(str, enum.Enum):
    """Keyword status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"


class KeywordSource(str, enum.Enum):
    """Keyword source enumeration."""
    AI_GENERATED = "ai-generated"
    MANUAL = "manual"


class BrandSafetyStatus(str, enum.Enum):
    """Brand safety classification."""
    SAFE = "safe"
    REVIEW = "review"
    UNSAFE = "unsafe"


class BrandSuitability(str, enum.Enum):
    """Brand suitability buckets."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Sentiment(str, enum.Enum):
    """Sentiment classification."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class TargetingRecommendation(str, enum.Enum):
    """Recommended targeting action."""
    STRONG_MATCH = "strong_match"
    MODERATE_MATCH = "moderate_match"
    WEAK_MATCH = "weak_match"
    AVOID = "avoid"


# Models
class Campaign(Base):
    """
    Campaign model representing a programmatic video campaign.
    
    Attributes:
        id: Primary key (UUID)
        name: Campaign name
        brand_name: Brand/company name
        brand_url: Brand website URL
        product_category: Product/service category
        campaign_goal: Campaign objective (awareness, consideration, conversion)
        campaign_definition: Detailed campaign description
        brand_context_text: Brand guidelines and context (from uploaded file or manual entry)
        status: Campaign status (draft, active, paused, completed)
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
    """
    __tablename__ = "campaigns"
    
    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Campaign information
    name = Column(String(255), nullable=False)
    brand_name = Column(String(255), nullable=False)
    brand_url = Column(Text, nullable=True)
    product_category = Column(String(255), nullable=False)
    campaign_goal = Column(String(255), nullable=False)
    campaign_definition = Column(Text, nullable=False)
    brand_context_text = Column(Text, nullable=True)

    # Status and metadata
    status = Column(Enum(CampaignStatus), default=CampaignStatus.DRAFT, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Neuro-contextual guidance
    audience_intent = Column(Text, nullable=True)
    audience_persona = Column(Text, nullable=True)
    tone_profile = Column(Text, nullable=True)
    emotion_guidance = Column(JSON, nullable=True)
    interest_guidance = Column(JSON, nullable=True)
    guardrail_terms = Column(JSON, nullable=True)
    inspiration_links = Column(JSON, nullable=True)
    primary_language = Column(String(5), nullable=True)
    primary_market = Column(String(5), nullable=True)

    # Relationships
    keywords = relationship("Keyword", back_populates="campaign", cascade="all, delete-orphan")
    videos = relationship("YouTubeVideo", back_populates="campaign", cascade="all, delete-orphan")
    channels = relationship("YouTubeChannel", back_populates="campaign", cascade="all, delete-orphan")
    avg_view_count = Column(Float, nullable=True)
    avg_like_count = Column(Float, nullable=True)
    avg_comment_count = Column(Float, nullable=True)
    
    def __repr__(self):
        return f"<Campaign(id={self.id}, name={self.name}, brand={self.brand_name})>"


class YouTubeChannel(Base):
    """
    YouTube channel model for storing discovered channel metadata.

    Attributes:
        id: Primary key (UUID)
        campaign_id: Foreign key to campaigns table
        channel_id: YouTube channel ID
        title: Channel title
        description: Channel description text
        custom_url: Vanity/custom URL if available
        country: Channel country if provided
        published_at: Channel creation date
        thumbnail_url: Default high-res thumbnail
        keywords: Channel keywords declared by creator
        topic_categories: YouTube provided topic categories
        subscriber_count: Subscriber count (may be hidden)
        view_count: Total channel views
        video_count: Total uploaded videos
        fetched_at: Timestamp of when the channel was stored
    """
    __tablename__ = "youtube_channels"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    channel_id = Column(String(30), unique=True, nullable=False, index=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    custom_url = Column(String(255), nullable=True)
    country = Column(String(5), nullable=True)
    published_at = Column(DateTime, nullable=True)
    thumbnail_url = Column(Text, nullable=True)
    keywords = Column(JSON, nullable=True)
    topic_categories = Column(JSON, nullable=True)

    subscriber_count = Column(Integer, nullable=True)
    view_count = Column(Integer, nullable=True)
    video_count = Column(Integer, nullable=True)

    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    campaign = relationship("Campaign", back_populates="channels")

    def __repr__(self):
        return f"<YouTubeChannel(channel_id={self.channel_id}, title={self.title})>"


class Keyword(Base):
    """
    Keyword model representing search keywords for YouTube video discovery.
    
    Attributes:
        id: Primary key (UUID)
        campaign_id: Foreign key to campaigns table
        keyword: The actual keyword text
        keyword_type: Type of keyword (core, long-tail, related, intent-based)
        relevance_score: AI-generated relevance score (0-1)
        source: Source of keyword (ai-generated, manual)
        status: Keyword status (active, inactive)
        created_at: Timestamp of creation
    """
    __tablename__ = "keywords"
    
    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign key
    campaign_id = Column(String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    
    # Keyword information
    keyword = Column(String(255), nullable=False)
    keyword_type = Column(Enum(KeywordType), nullable=False)
    relevance_score = Column(Float, nullable=False)  # 0-1 scale
    source = Column(Enum(KeywordSource), default=KeywordSource.AI_GENERATED, nullable=False)
    status = Column(Enum(KeywordStatus), default=KeywordStatus.ACTIVE, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_fetched_at = Column(DateTime, nullable=True)
    fetch_count = Column(Integer, default=0, nullable=False)
    total_results = Column(Integer, default=0, nullable=False)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="keywords")
    
    def __repr__(self):
        return f"<Keyword(id={self.id}, keyword={self.keyword}, type={self.keyword_type})>"


class YouTubeVideo(Base):
    """
    YouTube video model for storing fetched video metadata.
    
    Attributes:
        id: Primary key (UUID)
        campaign_id: Foreign key to campaigns table
        video_id: YouTube video ID (11 characters)
        channel_id: YouTube channel ID
        title: Video title
        description: Video description
        channel_title: Channel name
        tags: Video tags (JSON array)
        category: Video category ID
        duration: Video duration (ISO 8601 format)
        published_at: Publication timestamp
        view_count: Number of views
        like_count: Number of likes
        comment_count: Number of comments
        thumbnail_url: URL to video thumbnail
        fetched_at: Timestamp when video was fetched
    """
    __tablename__ = "youtube_videos"
    
    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign key
    campaign_id = Column(String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    
    # YouTube identifiers
    video_id = Column(String(20), unique=True, nullable=False, index=True)
    channel_id = Column(String(30), nullable=False, index=True)
    
    # Video metadata
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    channel_title = Column(String(255), nullable=True)
    tags = Column(JSON, nullable=True)
    category = Column(String(100), nullable=True)
    duration = Column(String(20), nullable=True)
    published_at = Column(DateTime, nullable=True)
    
    # Engagement metrics
    view_count = Column(BigInteger, default=0)
    like_count = Column(BigInteger, default=0)
    comment_count = Column(BigInteger, default=0)
    channel_view_count = Column(BigInteger, nullable=True)
    channel_subscriber_count = Column(BigInteger, nullable=True)
    
    # Media
    thumbnail_url = Column(Text, nullable=True)
    
    # Metadata
    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="videos")
    score = relationship("VideoScore", back_populates="video", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<YouTubeVideo(id={self.id}, video_id={self.video_id}, title={self.title[:50]})>"

    @property
    def average_view_ratio(self) -> Optional[float]:
        if not self.campaign or not getattr(self.campaign, "average_view_count", None):
            return None
        avg = self.campaign.average_view_count
        return self.view_count / avg if avg else None


class VideoScore(Base):
    """
    Stores Liz AI contextual scoring output for each video.
    """
    __tablename__ = "video_scores"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    video_id = Column(String(36), ForeignKey("youtube_videos.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    semantic_similarity_score = Column(Float, nullable=False)
    intent_score = Column(Float, nullable=False)
    interest_score = Column(Float, nullable=False)
    emotion_score = Column(Float, nullable=False)
    intent_type = Column(String(100), nullable=True)
    interest_topics = Column(JSON, default=list)
    emotion_type = Column(String(100), nullable=True)
    
    contextual_score = Column(Float, nullable=False)
    brand_safety_status = Column(Enum(BrandSafetyStatus), nullable=False)
    brand_suitability = Column(Enum(BrandSuitability), nullable=False)
    sentiment = Column(Enum(Sentiment), nullable=False)
    tone = Column(String(255), nullable=False)
    
    key_entities = Column(JSON, default=list)
    key_topics = Column(JSON, default=list)
    targeting_recommendation = Column(Enum(TargetingRecommendation), nullable=False)
    suggested_bid_modifier = Column(Float, nullable=False)
    
    reasoning = Column(Text, nullable=True)
    scored_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    campaign = relationship("Campaign")
    video = relationship("YouTubeVideo", back_populates="score")
    
    def __repr__(self):
        return f"<VideoScore(video_id={self.video_id}, contextual_score={self.contextual_score:.2f})>"
