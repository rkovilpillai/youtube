"""
Liz AI contextual scoring engine powered by GPT-4o.
Fetches extended metadata/transcripts via YouTube service and produces
multi-dimensional scores, with deterministic heuristics as fallback.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.config import settings
from api.models import (
    BrandSafetyStatus,
    BrandSuitability,
    Campaign,
    Sentiment,
    TargetingRecommendation,
    VideoScore,
    YouTubeVideo,
)
from api.services.youtube_service import youtube_service

logger = logging.getLogger(__name__)


class ScoringEngine:
    """Liz AI scoring engine with LLM + transcript awareness."""

    POSITIVE_TERMS = {
        "best",
        "ultimate",
        "win",
        "exciting",
        "innovative",
        "amazing",
        "love",
        "top",
        "guide",
        "review",
        "how",
    }
    NEGATIVE_TERMS = {
        "hate",
        "worst",
        "fail",
        "angry",
        "problem",
        "bad",
        "tragic",
        "disaster",
        "break",
        "complaint",
    }
    RISKY_TERMS = {
        "violence",
        "fight",
        "gun",
        "weapon",
        "leak",
        "politics",
        "nsfw",
        "accident",
        "gambling",
        "adult",
        "hate",
    }
    REVIEW_TERMS = {"prank", "drama", "controversy"}

    EMOTION_OPTIONS = [
        "joyful",
        "excited",
        "inspired",
        "nostalgic",
        "calm",
        "serious",
        "critical",
        "persuasive",
        "neutral",
    ]

    TONE_SUGGESTIONS = [
        "enthusiastic and informative",
        "promotional and enticing",
        "analytical and balanced",
        "critical and candid",
        "warm and conversational",
        "urgent and persuasive",
        "calm and reflective",
        "nostalgic and emotive",
    ]

    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.youtube_service = youtube_service

    # ------------------------------------------------------------------
    # Heuristic helpers (used for prompt context + fallback)
    # ------------------------------------------------------------------
    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[a-z0-9]+", (text or "").lower())

    def _aggregate_video_text(self, video: YouTubeVideo) -> str:
        tags = " ".join(video.tags or []) if isinstance(video.tags, list) else ""
        return f"{video.title} {video.description or ''} {tags}"

    def _aggregate_campaign_text(self, campaign: Campaign) -> str:
        return " ".join(
            filter(
                None,
                [
                    campaign.name,
                    campaign.brand_name,
                    campaign.product_category,
                    campaign.campaign_goal,
                    campaign.campaign_definition,
                    campaign.brand_context_text or "",
                ],
            )
        )

    def _heuristic_nlp(self, campaign: Campaign, video: YouTubeVideo) -> Dict[str, Any]:
        video_tokens = self._tokenize(self._aggregate_video_text(video))
        campaign_tokens = self._tokenize(self._aggregate_campaign_text(campaign))

        video_set = set(video_tokens)
        campaign_set = set(campaign_tokens)
        if not video_set or not campaign_set:
            similarity = 0.0
        else:
            similarity = len(video_set & campaign_set) / len(video_set | campaign_set)

        similarity = min(max(similarity, 0.0), 1.0)

        intent_terms = {"how", "review", "guide", "tutorial", "tips", "versus", "compare"}
        intent_hits = len(intent_terms & video_set)
        intent_score = min(1.0, 0.35 + intent_hits * 0.1 + similarity * 0.4)

        tag_bonus = min(0.25, (len(video.tags or []) * 0.02))
        interest_score = min(1.0, similarity * 0.7 + tag_bonus + 0.1)

        positive_hits = sum(1 for token in video_tokens if token in self.POSITIVE_TERMS)
        negative_hits = sum(1 for token in video_tokens if token in self.NEGATIVE_TERMS)
        total_hits = positive_hits + negative_hits or 1
        emotion_score = min(1.0, max(0.1, (positive_hits + 1) / (total_hits + 1)))

        if positive_hits > negative_hits + 1:
            sentiment = Sentiment.POSITIVE
        elif negative_hits > positive_hits + 1:
            sentiment = Sentiment.NEGATIVE
        else:
            sentiment = Sentiment.NEUTRAL

        tone = self._infer_tone(sentiment, video_tokens)

        key_topics = list(sorted(video_set & campaign_set, key=len, reverse=True))[:5]
        if not key_topics and video.tags:
            key_topics = video.tags[:5]

        key_entities: List[str] = []
        for word in self._tokenize(video.title):
            if len(word) > 3 and word not in key_entities:
                key_entities.append(word)
            if len(key_entities) == 3:
                break

        intent_type = self._infer_intent_type(video_tokens)
        interest_topics = self._infer_interest_topics(video)
        emotion_type = self._infer_emotion_type(sentiment, video_tokens)

        return {
            "semantic_similarity_score": round(similarity, 3),
            "intent_score": round(intent_score, 3),
            "interest_score": round(interest_score, 3),
            "emotion_score": round(emotion_score, 3),
            "sentiment": sentiment,
            "tone": tone,
            "key_topics": key_topics or list(video_set)[:5],
            "key_entities": key_entities or key_topics[:3],
            "intent_type": intent_type,
            "interest_topics": interest_topics,
            "emotion_type": emotion_type,
        }

    def _heuristic_brand_safety(
        self, video: YouTubeVideo, sentiment: Sentiment
    ) -> Dict[str, Any]:
        text = self._aggregate_video_text(video).lower()
        status = BrandSafetyStatus.SAFE
        if any(term in text for term in self.RISKY_TERMS):
            status = BrandSafetyStatus.UNSAFE
        elif any(term in text for term in self.REVIEW_TERMS) or sentiment == Sentiment.NEGATIVE:
            status = BrandSafetyStatus.REVIEW
        return {"brand_safety_status": status}

    def _determine_recommendation(
        self,
        contextual_score: float,
        brand_suitability: BrandSuitability,
        brand_safety_status: BrandSafetyStatus,
    ) -> Tuple[TargetingRecommendation, float]:
        if brand_safety_status == BrandSafetyStatus.UNSAFE:
            return TargetingRecommendation.AVOID, 0.0
        if contextual_score >= 0.8 and brand_suitability == BrandSuitability.HIGH:
            return TargetingRecommendation.STRONG_MATCH, 1.35
        if contextual_score >= 0.6 and brand_suitability in (
            BrandSuitability.HIGH,
            BrandSuitability.MEDIUM,
        ):
            return TargetingRecommendation.MODERATE_MATCH, 1.1
        if contextual_score >= 0.4:
            return TargetingRecommendation.WEAK_MATCH, 0.9
        return TargetingRecommendation.AVOID, 0.0

    def _determine_brand_suitability(
        self, contextual_score: float, brand_safety_status: BrandSafetyStatus, sentiment: Sentiment
    ) -> BrandSuitability:
        if brand_safety_status == BrandSafetyStatus.UNSAFE:
            return BrandSuitability.LOW
        if contextual_score >= 0.75 and sentiment == Sentiment.POSITIVE:
            return BrandSuitability.HIGH
        if contextual_score >= 0.5:
            return BrandSuitability.MEDIUM
        return BrandSuitability.LOW

    def _infer_intent_type(self, video_tokens: List[str]) -> str:
        if any(term in video_tokens for term in ["buy", "deal", "sale", "price", "review", "vs"]):
            return "commercial"
        if any(term in video_tokens for term in ["how", "guide", "tips", "tutorial"]):
            return "informational"
        return "entertainment"

    def _infer_interest_topics(self, video: YouTubeVideo) -> List[str]:
        if video.tags:
            return video.tags[:3]
        tokens = self._tokenize(video.title)
        return list(dict.fromkeys(tokens[:3]))

    def _infer_emotion_type(self, sentiment: Sentiment, video_tokens: List[str]) -> str:
        tokens = set(video_tokens)
        if sentiment == Sentiment.NEGATIVE:
            return "critical"
        if any(term in tokens for term in ["unboxing", "launch", "premiere", "event", "live"]):
            return "excited"
        if any(term in tokens for term in ["deal", "offer", "sale", "discount", "buy", "best"]):
            return "persuasive"
        if any(term in tokens for term in ["how", "guide", "tutorial", "learn", "tips"]):
            return "inspired"
        if any(term in tokens for term in ["history", "retro", "throwback", "classic", "nostalgia"]):
            return "nostalgic"
        if any(term in tokens for term in ["relax", "relaxing", "meditation", "ambient", "calm"]):
            return "calm"
        if any(term in tokens for term in ["analysis", "review", "breakdown", "comparison", "vs"]):
            return "serious"
        if sentiment == Sentiment.POSITIVE:
            return "joyful"
        return "neutral"

    def _infer_tone(self, sentiment: Sentiment, video_tokens: List[str]) -> str:
        tokens = set(video_tokens)
        if any(term in tokens for term in ["unboxing", "launch", "event", "live"]):
            return "enthusiastic and informative"
        if any(term in tokens for term in ["deal", "offer", "sale", "discount", "buy"]):
            return "urgent and persuasive"
        if any(term in tokens for term in ["review", "analysis", "breakdown", "comparison", "vs"]):
            return "analytical and balanced"
        if any(term in tokens for term in ["history", "retro", "classic", "nostalgia"]):
            return "nostalgic and emotive"
        if any(term in tokens for term in ["calm", "relax", "meditation", "ambient"]):
            return "calm and reflective"
        if sentiment == Sentiment.NEGATIVE:
            return "critical and candid"
        if any(term in tokens for term in ["tips", "guide", "tutorial", "learn"]):
            return "warm and conversational"
        return "promotional and enticing"

    # ------------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------------
    def _truncate_text(self, text: str, max_chars: int = 5000) -> str:
        if not text:
            return ""
        return text if len(text) <= max_chars else text[:max_chars] + "..."

    def _enum_value(self, enum_cls, value: str, default):
        if isinstance(value, enum_cls):
            return value
        if isinstance(value, str):
            cleaned = value.strip().lower()
            for member in enum_cls:
                if member.value == cleaned:
                    return member
        return default

    def _coerce_float(self, value: Any, default: float, clamp: Tuple[float, float] = (0.0, 1.0)) -> float:
        try:
            num = float(value)
            return max(clamp[0], min(clamp[1], num))
        except Exception:
            return default

    def _coerce_topics(self, value: Any, fallback: List[str]) -> List[str]:
        if isinstance(value, list):
            cleaned = [str(v) for v in value if v]
            return cleaned[:3] if cleaned else fallback
        if isinstance(value, str) and value.strip():
            parts = [part.strip() for part in value.split(',') if part.strip()]
            return parts[:3] if parts else fallback
        return fallback

    def _normalize_emotion(self, value: Any, fallback: str) -> str:
        if isinstance(value, str):
            cleaned = value.strip().lower()
            for option in self.EMOTION_OPTIONS:
                if cleaned == option:
                    return option
            # Try to map common synonyms
            synonyms = {
                "happy": "joyful",
                "cheerful": "joyful",
                "exciting": "excited",
                "energetic": "excited",
                "motivated": "inspired",
                "emotional": "nostalgic",
                "relaxed": "calm",
                "informative": "serious",
                "negative": "critical",
                "sales": "persuasive",
            }
            if cleaned in synonyms:
                return synonyms[cleaned]
        return fallback if fallback in self.EMOTION_OPTIONS else "neutral"

    def _build_prompt(
        self,
        campaign: Campaign,
        video: YouTubeVideo,
        metadata: Dict[str, Any],
        transcript: str,
        heuristic: Dict[str, Any],
    ) -> str:
        transcript_excerpt = self._truncate_text(transcript)
        metadata_lines = [
            f"Title: {metadata.get('title') or video.title}",
            f"Channel: {metadata.get('channel_title') or video.channel_title}",
            f"Views: {metadata.get('view_count', video.view_count)}",
            f"Likes: {metadata.get('like_count', video.like_count)}",
            f"Comments: {metadata.get('comment_count', video.comment_count)}",
            f"Published: {metadata.get('published_at')}",
            f"Duration: {metadata.get('duration')}",
            f"Tags: {', '.join(metadata.get('tags', []) or video.tags or [])[:500]}",
        ]
        heuristic_section = json.dumps(
            {
                "baseline_semantic_similarity": heuristic["semantic_similarity_score"],
                "baseline_intent_score": heuristic["intent_score"],
                "baseline_interest_score": heuristic["interest_score"],
                "baseline_emotion_score": heuristic["emotion_score"],
                "baseline_sentiment": heuristic["sentiment"].value,
                "baseline_tone": heuristic["tone"],
            },
            ensure_ascii=False,
        )

        return f"""
You are Liz AI, an expert contextual advertising analyst.
Use the campaign brief, video metadata, and transcript excerpt to rate the video.

Campaign:
- Name: {campaign.name}
- Brand: {campaign.brand_name}
- Goal: {campaign.campaign_goal}
- Product Category: {campaign.product_category}
- Definition: {campaign.campaign_definition}
- Brand Context: {campaign.brand_context_text or 'Not provided'}

Video Metadata:
{chr(10).join(metadata_lines)}

Transcript Excerpt:
{transcript_excerpt or 'Transcript unavailable'}

Baseline signals (for reference only, do not copy):
{heuristic_section}

Return STRICT JSON with these keys and ranges:
{{
  "semantic_similarity_score": 0-1 float,
  "intent_score": 0-1 float,
  "interest_score": 0-1 float,
  "emotion_score": 0-1 float,
  "intent_type": "commercial|informational|entertainment",
  "interest_topics": ["topic", ... up to 3 entries],
  "emotion_type": "joyful|excited|inspired|nostalgic|calm|serious|critical|persuasive|neutral",
  "contextual_score": 0-1 float,
  "brand_safety_status": "safe|review|unsafe",
  "brand_suitability": "high|medium|low",
  "sentiment": "positive|neutral|negative",
  "tone": "short descriptive string (choose from or blend: enthusiastic and informative, promotional and enticing, analytical and balanced, critical and candid, warm and conversational, urgent and persuasive, calm and reflective, nostalgic and emotive)",
  "key_entities": ["entity", ...],
  "key_topics": ["topic", ...],
  "targeting_recommendation": "strong_match|moderate_match|weak_match|avoid",
  "suggested_bid_modifier": float between 0 and 2,
  "reasoning": "2-3 concise sentences"
}}
No additional commentary.
"""

    def _call_llm(
        self,
        campaign: Campaign,
        video: YouTubeVideo,
        metadata: Dict[str, Any],
        transcript: str,
        heuristic: Dict[str, Any],
    ) -> Dict[str, Any]:
        prompt = self._build_prompt(campaign, video, metadata, transcript, heuristic)
        response = self.client.chat.completions.create(
            model=settings.openai_model,
            temperature=settings.openai_temperature,
            max_tokens=settings.openai_max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are Liz AI, a contextual marketing analyst."},
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content
        return json.loads(content)

    def _payload_from_llm(self, llm_payload: Dict[str, Any], heuristic: Dict[str, Any]) -> Dict[str, Any]:
        semantic = self._coerce_float(
            llm_payload.get("semantic_similarity_score"),
            default=heuristic["semantic_similarity_score"],
        )
        intent = self._coerce_float(
            llm_payload.get("intent_score"),
            default=heuristic["intent_score"],
        )
        interest = self._coerce_float(
            llm_payload.get("interest_score"),
            default=heuristic["interest_score"],
        )
        emotion = self._coerce_float(
            llm_payload.get("emotion_score"),
            default=heuristic["emotion_score"],
        )
        contextual = self._coerce_float(
            llm_payload.get("contextual_score"),
            default=(semantic * 0.4 + intent * 0.25 + interest * 0.2 + emotion * 0.15),
        )

        brand_safety = self._enum_value(
            BrandSafetyStatus,
            llm_payload.get("brand_safety_status"),
            BrandSafetyStatus.SAFE,
        )
        sentiment = self._enum_value(
            Sentiment,
            llm_payload.get("sentiment"),
            heuristic["sentiment"],
        )
        brand_suitability = self._enum_value(
            BrandSuitability,
            llm_payload.get("brand_suitability"),
            self._determine_brand_suitability(contextual, brand_safety, sentiment),
        )

        recommendation = self._enum_value(
            TargetingRecommendation,
            llm_payload.get("targeting_recommendation"),
            None,
        )
        bid_modifier = float(llm_payload.get("suggested_bid_modifier", 1.0))
        if recommendation is None:
            recommendation, bid_modifier = self._determine_recommendation(
                contextual, brand_suitability, brand_safety
            )

        return {
            "semantic_similarity_score": semantic,
            "intent_score": intent,
            "interest_score": interest,
            "emotion_score": emotion,
            "intent_type": (llm_payload.get("intent_type") or heuristic["intent_type"]),
            "interest_topics": self._coerce_topics(
                llm_payload.get("interest_topics"), heuristic["interest_topics"]
            ),
            "emotion_type": self._normalize_emotion(
                llm_payload.get("emotion_type"), heuristic["emotion_type"]
            ),
            "contextual_score": contextual,
            "brand_safety_status": brand_safety,
            "brand_suitability": brand_suitability,
            "sentiment": sentiment,
            "tone": llm_payload.get("tone") or heuristic["tone"],
            "key_entities": llm_payload.get("key_entities") or heuristic["key_entities"],
            "key_topics": llm_payload.get("key_topics") or heuristic["key_topics"],
            "targeting_recommendation": recommendation,
            "suggested_bid_modifier": round(max(0.0, min(2.0, bid_modifier)), 2),
            "reasoning": llm_payload.get("reasoning")
            or self._build_reasoning_placeholder(contextual, recommendation),
        }

    def _build_reasoning_placeholder(
        self, contextual_score: float, recommendation: TargetingRecommendation
    ) -> str:
        return (
            f"Contextual score {contextual_score:.2f} justifies {recommendation.value.replace('_', ' ')} "
            "based on semantic overlap, intent alignment, and emotional fit."
        )

    def _fallback_payload(
        self,
        campaign: Campaign,
        video: YouTubeVideo,
        heuristic: Dict[str, Any],
    ) -> Dict[str, Any]:
        brand = self._heuristic_brand_safety(video, heuristic["sentiment"])
        contextual = (
            heuristic["semantic_similarity_score"] * 0.40
            + heuristic["intent_score"] * 0.25
            + heuristic["interest_score"] * 0.20
            + heuristic["emotion_score"] * 0.15
        )
        suitability = self._determine_brand_suitability(
            contextual, brand["brand_safety_status"], heuristic["sentiment"]
        )
        recommendation, bid = self._determine_recommendation(
            contextual, suitability, brand["brand_safety_status"]
        )
        return {
            "semantic_similarity_score": heuristic["semantic_similarity_score"],
            "intent_score": heuristic["intent_score"],
            "interest_score": heuristic["interest_score"],
            "emotion_score": heuristic["emotion_score"],
            "intent_type": heuristic["intent_type"],
            "interest_topics": heuristic["interest_topics"],
            "emotion_type": self._normalize_emotion(heuristic["emotion_type"], "neutral"),
            "contextual_score": round(contextual, 3),
            "brand_safety_status": brand["brand_safety_status"],
            "brand_suitability": suitability,
            "sentiment": heuristic["sentiment"],
            "tone": heuristic["tone"],
            "key_entities": heuristic["key_entities"],
            "key_topics": heuristic["key_topics"],
            "targeting_recommendation": recommendation,
            "suggested_bid_modifier": bid,
            "reasoning": self._build_reasoning(campaign, video, contextual, recommendation),
        }

    def _build_reasoning(
        self,
        campaign: Campaign,
        video: YouTubeVideo,
        contextual_score: float,
        recommendation: TargetingRecommendation,
    ) -> str:
        return (
            f"Video '{video.title[:60]}' aligns {contextual_score:.0%} with campaign '{campaign.name}'. "
            f"Recommendation: {recommendation.value.replace('_', ' ')} based on topical and sentiment fit."
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def score_video(
        self,
        db: Session,
        campaign: Campaign,
        video: YouTubeVideo,
        use_transcript: bool = True,
    ) -> VideoScore:
        """Score a video using GPT-4o; gracefully degrade to heuristics if needed."""
        heuristic = self._heuristic_nlp(campaign, video)

        metadata: Dict[str, Any] = {
            "video_id": video.video_id,
            "channel_id": video.channel_id,
            "channel_title": video.channel_title,
            "title": video.title,
            "description": video.description or "",
            "tags": video.tags or [],
            "published_at": video.published_at.isoformat() if video.published_at else None,
            "view_count": video.view_count,
            "like_count": video.like_count,
            "comment_count": video.comment_count,
            "duration": video.duration,
            "channel_subscriber_count": getattr(video, "channel_subscriber_count", None),
            "channel_view_count": getattr(video, "channel_view_count", None),
        }
        transcript = ""
        preferred_languages: Optional[List[str]] = None
        if use_transcript:
            try:
                potential_languages: List[str] = []
                if campaign.primary_language:
                    primary = campaign.primary_language.lower()
                    potential_languages.append(primary)
                    potential_languages.append(f"{primary}-{campaign.primary_language.upper()}")
                potential_languages.extend(["en", "en-US"])

                seen_langs: set[str] = set()
                ordered_langs: List[str] = []
                for lang in potential_languages:
                    if not lang or lang in seen_langs:
                        continue
                    seen_langs.add(lang)
                    ordered_langs.append(lang)
                preferred_languages = ordered_langs

                transcript_data = self.youtube_service.get_video_transcript(
                    video.video_id,
                    languages=preferred_languages,
                )
                transcript = transcript_data.get("text", "")
                if not metadata.get("channel_subscriber_count") and metadata.get("channel_id"):
                    channel_stats = self.youtube_service.get_channel_statistics(metadata["channel_id"])
                    metadata["channel_subscriber_count"] = channel_stats.get("subscriberCount")
                    metadata["channel_view_count"] = channel_stats.get("viewCount")
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to fetch transcript for %s: %s", video.video_id, exc)

        llm_payload: Dict[str, Any] | None = None
        if metadata or transcript:
            try:
                llm_payload = self._call_llm(campaign, video, metadata, transcript, heuristic)
                logger.info("LLM scoring succeeded for video %s", video.video_id)
            except Exception as exc:  # pragma: no cover - depends on API
                logger.error("LLM scoring failed for %s: %s", video.video_id, exc)
        else:
            logger.info("Metadata/transcript unavailable for %s, using heuristics", video.video_id)

        payload = (
            self._payload_from_llm(llm_payload, heuristic)
            if llm_payload
            else self._fallback_payload(campaign, video, heuristic)
        )

        existing = (
            db.query(VideoScore)
            .filter(VideoScore.video_id == video.id, VideoScore.campaign_id == campaign.id)
            .first()
        )

        if existing:
            for field, value in payload.items():
                setattr(existing, field, value)
            existing.scored_at = datetime.utcnow()
            record = existing
        else:
            record = VideoScore(
                campaign_id=campaign.id,
                video_id=video.id,
                scored_at=datetime.utcnow(),
                **payload,
            )
            db.add(record)

        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            logger.warning(
                "Score insert conflict for video %s (campaign %s): %s", video.video_id, campaign.id, exc
            )
            record = (
                db.query(VideoScore)
                .filter(VideoScore.video_id == video.id, VideoScore.campaign_id == campaign.id)
                .first()
            )
            if record is None:
                raise
            for field, value in payload.items():
                setattr(record, field, value)
            record.scored_at = datetime.utcnow()
            db.commit()

        db.refresh(record)
        return record


# Global instance
scoring_engine = ScoringEngine()
