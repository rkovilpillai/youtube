"""
YouTube Service - Integration with YouTube Data API v3.
Handles video fetching, metadata retrieval, and channel information.
"""
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
import logging
from collections import defaultdict
import shlex

from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    CouldNotRetrieveTranscript
)

from api.config import settings
from api.models import YouTubeVideo, YouTubeChannel, Keyword, KeywordStatus, KeywordType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


KEYWORD_TYPE_WEIGHTS = {
    KeywordType.CORE: 0.50,
    KeywordType.RELATED: 0.25,
    KeywordType.INTENT_BASED: 0.15,
    KeywordType.LONG_TAIL: 0.10,
}


class YouTubeService:
    """
    Service for interacting with YouTube Data API v3.
    
    Features:
    - Search videos by keywords
    - Fetch video details and metadata
    - Retrieve channel information
    - Track API quota usage
    """
    
    def __init__(self):
        """Initialize YouTube API client."""
        try:
            self.youtube = build('youtube', 'v3', developerKey=settings.youtube_api_key)
            self.quota_used = 0
            logger.info("✅ YouTube API client initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize YouTube API client: {e}")
            raise Exception(f"YouTube API initialization failed: {str(e)}")

    def _select_keywords_for_rotation(
        self,
        keywords: List[Keyword],
        max_keyword_budget: int = 20,
        weight_map: Optional[Dict[KeywordType, float]] = None
    ) -> Tuple[List[Keyword], Dict[KeywordType, int]]:
        """
        Select a diversified set of keywords for search rotation.

        Args:
            keywords: Active keyword objects for a campaign.
            max_keyword_budget: Maximum number of keywords to rotate through.
            weight_map: Optional weighting (0-1 range, not required to sum to 1) per keyword type.
                        Higher weights receive more slots before graceful fallbacks fill the rest.

        Returns:
            Tuple of (selected keywords, selection mix summary).
        """
        if not keywords:
            raise ValueError("No active keywords found for campaign")

        max_keyword_budget = min(len(keywords), max_keyword_budget)
        if max_keyword_budget <= 0:
            raise ValueError("No eligible keywords available for selection")

        keywords_by_type: Dict[KeywordType, List[Keyword]] = defaultdict(list)
        for kw in keywords:
            keywords_by_type[kw.keyword_type].append(kw)

        def keyword_priority_key(kw: Keyword):
            total_results = kw.total_results or 0
            last_fetch = kw.last_fetched_at or datetime.min
            return (total_results, last_fetch, -kw.relevance_score)

        for kw_type in keywords_by_type:
            keywords_by_type[kw_type].sort(key=keyword_priority_key)

        ordered_types = [
            KeywordType.CORE,
            KeywordType.RELATED,
            KeywordType.INTENT_BASED,
            KeywordType.LONG_TAIL,
        ]
        available_types = [kw_type for kw_type in ordered_types if keywords_by_type.get(kw_type)]
        extra_types = [kw_type for kw_type in keywords_by_type.keys() if kw_type not in available_types]
        available_types.extend(extra_types)
        if not available_types:
            raise ValueError("Unable to select keywords for fetch request")

        weights = weight_map or {}
        positive_weight_sum = sum(max(weights.get(kw_type, 0.0), 0.0) for kw_type in available_types)
        if positive_weight_sum <= 0:
            normalized_weights = {kw_type: 1.0 / len(available_types) for kw_type in available_types}
        else:
            normalized_weights = {
                kw_type: max(weights.get(kw_type, 0.0), 0.0) / positive_weight_sum
                for kw_type in available_types
            }

        allocation: Dict[KeywordType, int] = {kw_type: 0 for kw_type in available_types}
        fractional_allocation: List[Tuple[float, KeywordType]] = []
        total_assigned = 0

        for kw_type in available_types:
            desired = max_keyword_budget * normalized_weights.get(kw_type, 0.0)
            base_take = min(len(keywords_by_type[kw_type]), int(desired))
            allocation[kw_type] = base_take
            total_assigned += base_take
            fractional_allocation.append((desired - base_take, kw_type))

        remaining_slots = max_keyword_budget - total_assigned

        # Allocate remaining slots by descending fractional remainder while respecting bucket capacity.
        if remaining_slots > 0:
            fractional_allocation.sort(reverse=True)
            idx = 0
            iterations = 0
            max_iterations = max(len(fractional_allocation) * 5, 1)
            while remaining_slots > 0 and fractional_allocation and iterations < max_iterations:
                fraction, kw_type = fractional_allocation[idx % len(fractional_allocation)]
                if allocation[kw_type] < len(keywords_by_type[kw_type]):
                    allocation[kw_type] += 1
                    remaining_slots -= 1
                idx += 1
                iterations += 1

        # Graceful fallback: if slots remain, distribute by weight priority wherever capacity exists.
        if remaining_slots > 0:
            prioritized_types = sorted(
                available_types,
                key=lambda t: (normalized_weights.get(t, 0.0), len(keywords_by_type[t])),
                reverse=True
            )
            for kw_type in prioritized_types:
                while remaining_slots > 0 and allocation[kw_type] < len(keywords_by_type[kw_type]):
                    allocation[kw_type] += 1
                    remaining_slots -= 1
            # As a final guard, if slots still remain (unlikely), fall back to any remaining keywords.

        selected_keywords: List[Keyword] = []
        selection_summary: Dict[KeywordType, int] = defaultdict(int)
        selected_ids: Set[str] = set()

        for kw_type in available_types:
            bucket = keywords_by_type[kw_type]
            take = min(allocation.get(kw_type, 0), len(bucket))
            for kw in bucket[:take]:
                if kw.id not in selected_ids:
                    selected_keywords.append(kw)
                    selection_summary[kw.keyword_type] += 1
                    selected_ids.add(kw.id)

        if len(selected_keywords) < max_keyword_budget:
            remaining_needed = max_keyword_budget - len(selected_keywords)
            leftover_candidates: List[Keyword] = []
            for kw_type, bucket in keywords_by_type.items():
                leftover_candidates.extend(bucket[allocation.get(kw_type, 0):])
            leftover_candidates.sort(key=keyword_priority_key)
            for kw in leftover_candidates:
                if kw.id in selected_ids:
                    continue
                selected_keywords.append(kw)
                selection_summary[kw.keyword_type] += 1
                selected_ids.add(kw.id)
                remaining_needed -= 1
                if remaining_needed <= 0:
                    break

        if not selected_keywords:
            raise ValueError("Unable to select keywords for fetch request")

        return selected_keywords, selection_summary
    
    def search_videos(
        self,
        keywords: List[str],
        max_results_per_keyword: int = 10,
        language: str = "en",
        region: str = "US",
        published_after: Optional[datetime] = None,
        published_before: Optional[datetime] = None,
        order: str = "relevance",
        video_duration: Optional[str] = None,
        video_definition: Optional[str] = None
    ) -> Tuple[List[str], Dict[str, List[str]]]:
        """
        Search for videos using keywords.
        
        Args:
            keywords: List of search keywords
            max_results_per_keyword: Maximum videos per keyword (1-50)
            language: Language code (ISO 639-1)
            region: Region code (ISO 3166-1 alpha-2)
            published_after: Filter videos after this date
            published_before: Filter videos before this date
            order: Sort order (relevance, date, rating, viewCount, title)
            video_duration: Duration filter (any, short, medium, long)
            video_definition: Definition filter (any, standard, high)
        
        Returns:
            Tuple containing:
                - List of unique video IDs across all keywords
                - Mapping of keyword -> list of video IDs returned for that keyword
        """
        all_video_ids = set()
        keyword_results: Dict[str, List[str]] = {}
        
        for keyword in keywords:
            try:
                logger.info(f"Searching videos for keyword: {keyword}")
                
                # Build search parameters
                search_params = {
                    'part': 'id',
                    'q': keyword,
                    'type': 'video',
                    'maxResults': min(max_results_per_keyword, 50),
                    'relevanceLanguage': language,
                    'regionCode': region,
                    'videoEmbeddable': 'true',  # Only embeddable videos
                    'videoSyndicated': 'true'   # Only syndicated videos
                }

                # Optional filters
                if order:
                    search_params['order'] = order
                if video_duration and video_duration != "any":
                    search_params['videoDuration'] = video_duration
                if video_definition and video_definition != "any":
                    search_params['videoDefinition'] = video_definition
                
                # Add date filters if provided
                if published_after:
                    search_params['publishedAfter'] = published_after.isoformat() + 'Z'
                if published_before:
                    search_params['publishedBefore'] = published_before.isoformat() + 'Z'
                
                # Execute search
                search_request = self.youtube.search().list(**search_params)
                search_response = search_request.execute()
                
                # Track quota usage (search costs 100 units)
                self.quota_used += 100
                
                # Extract video IDs
                video_ids = [
                    item['id']['videoId'] 
                    for item in search_response.get('items', [])
                    if item['id']['kind'] == 'youtube#video'
                ]
                
                all_video_ids.update(video_ids)
                keyword_results[keyword] = video_ids
                logger.info(f"Found {len(video_ids)} videos for keyword: {keyword}")
                
            except HttpError as e:
                logger.error(f"YouTube API error for keyword '{keyword}': {e}")
                if e.resp.status == 403:
                    logger.error("Quota exceeded or API key invalid!")
                    raise Exception("YouTube API quota exceeded or invalid API key")
                keyword_results[keyword] = []
                continue
            except Exception as e:
                logger.error(f"Unexpected error searching for '{keyword}': {e}")
                keyword_results[keyword] = []
                continue
        
        logger.info(f"Total unique videos found: {len(all_video_ids)}")
        return list(all_video_ids), keyword_results

    def search_channels(
        self,
        keywords: List[str],
        max_results_per_keyword: int = 10,
        language: str = "en",
        region: str = "US",
        order: str = "relevance"
    ) -> Tuple[List[str], Dict[str, List[str]]]:
        """
        Search for channels using campaign keywords.

        Args:
            keywords: List of search keywords.
            max_results_per_keyword: Maximum channels per keyword (1-50).
            language: Language bias (ISO 639-1).
            region: Region code (ISO 3166-1 alpha-2).
            order: Sort order (relevance, date, rating, viewCount, videoCount).

        Returns:
            Tuple containing:
                - List of unique channel IDs.
                - Mapping of keyword -> channel IDs returned.
        """
        all_channel_ids = set()
        keyword_results: Dict[str, List[str]] = {}

        for keyword in keywords:
            try:
                logger.info(f"Searching channels for keyword: {keyword}")

                search_params = {
                    'part': 'id',
                    'q': keyword,
                    'type': 'channel',
                    'maxResults': min(max_results_per_keyword, 50),
                    'relevanceLanguage': language,
                    'regionCode': region,
                    'order': order
                }

                search_request = self.youtube.search().list(**search_params)
                search_response = search_request.execute()

                # Track quota usage (search.list costs 100 units regardless of type)
                self.quota_used += 100

                channel_ids = [
                    item['id']['channelId']
                    for item in search_response.get('items', [])
                    if item['id']['kind'] == 'youtube#channel'
                ]

                all_channel_ids.update(channel_ids)
                keyword_results[keyword] = channel_ids
                logger.info(f"Found {len(channel_ids)} channels for keyword: {keyword}")

            except HttpError as e:
                logger.error(f"YouTube API error for channel keyword '{keyword}': {e}")
                if e.resp.status == 403:
                    logger.error("Quota exceeded or API key invalid!")
                    raise Exception("YouTube API quota exceeded or invalid API key")
                keyword_results[keyword] = []
                continue
            except Exception as e:
                logger.error(f"Unexpected error searching channels for '{keyword}': {e}")
                keyword_results[keyword] = []
                continue

        logger.info(f"Total unique channels found: {len(all_channel_ids)}")
        return list(all_channel_ids), keyword_results

    def get_channel_statistics(self, channel_id: str) -> Dict[str, Any]:
        """Retrieve channel statistics (subscriber/view counts)."""
        if not hasattr(self, "_channel_stats_cache"):
            self._channel_stats_cache = {}
        if channel_id in self._channel_stats_cache:
            return self._channel_stats_cache[channel_id]

        try:
            request = self.youtube.channels().list(
                part='statistics',
                id=channel_id
            )
            response = request.execute()
            self.quota_used += 1
            items = response.get('items', [])
            if items:
                stats = items[0].get('statistics', {})
                data = {
                    'viewCount': stats.get('viewCount'),
                    'subscriberCount': stats.get('subscriberCount'),
                    'videoCount': stats.get('videoCount')
                }
                self._channel_stats_cache[channel_id] = data
                return data
        except Exception as exc:
            logger.warning(f"Failed to fetch channel stats for {channel_id}: {exc}")

        return {}

    def get_channel_details(self, channel_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Retrieve detailed channel metadata and statistics.

        Args:
            channel_ids: List of YouTube channel IDs (max 50 per request)

        Returns:
            List of channel data dictionaries ready for persistence.
        """
        if not channel_ids:
            return []

        channel_data_list: List[Dict[str, Any]] = []
        batch_size = 50

        for i in range(0, len(channel_ids), batch_size):
            batch = channel_ids[i:i + batch_size]
            try:
                logger.info(f"Fetching details for {len(batch)} channels (batch {i // batch_size + 1})")
                request = self.youtube.channels().list(
                    part='snippet,statistics,brandingSettings,topicDetails',
                    id=','.join(batch)
                )
                response = request.execute()

                # Track quota usage (channels.list costs 1 unit per channel in the batch)
                self.quota_used += len(batch)

                for item in response.get('items', []):
                    try:
                        snippet = item.get('snippet', {}) or {}
                        statistics = item.get('statistics', {}) or {}
                        branding = (item.get('brandingSettings', {}) or {}).get('channel', {}) or {}
                        topic_details = item.get('topicDetails', {}) or {}

                        channel_id = item.get('id')
                        if not channel_id:
                            continue

                        keywords_raw = branding.get('keywords')
                        keywords_list = None
                        if keywords_raw:
                            try:
                                keywords_list = shlex.split(keywords_raw)
                            except ValueError:
                                keywords_list = [kw.strip() for kw in keywords_raw.split(",") if kw.strip()]

                        topic_categories = topic_details.get('topicCategories')
                        if topic_categories:
                            topic_categories = [topic for topic in topic_categories if topic]

                        thumbnail_url = None
                        thumbnails = snippet.get('thumbnails', {})
                        for preferred_key in ('high', 'medium', 'default'):
                            if thumbnails.get(preferred_key, {}).get('url'):
                                thumbnail_url = thumbnails[preferred_key]['url']
                                break

                        subscriber_count = statistics.get('subscriberCount')
                        if subscriber_count is not None:
                            try:
                                subscriber_count = int(subscriber_count)
                            except (TypeError, ValueError):
                                subscriber_count = None

                        view_count = statistics.get('viewCount')
                        if view_count is not None:
                            try:
                                view_count = int(view_count)
                            except (TypeError, ValueError):
                                view_count = None

                        video_count = statistics.get('videoCount')
                        if video_count is not None:
                            try:
                                video_count = int(video_count)
                            except (TypeError, ValueError):
                                video_count = None

                        if not hasattr(self, "_channel_stats_cache"):
                            self._channel_stats_cache = {}
                        self._channel_stats_cache[channel_id] = {
                            'subscriberCount': subscriber_count,
                            'viewCount': view_count,
                            'videoCount': video_count
                        }

                        channel_data_list.append({
                            'channel_id': channel_id,
                            'title': snippet.get('title', ''),
                            'description': snippet.get('description'),
                            'custom_url': snippet.get('customUrl'),
                            'country': snippet.get('country'),
                            'published_at': self._parse_datetime(snippet.get('publishedAt')),
                            'thumbnail_url': thumbnail_url,
                            'keywords': keywords_list,
                            'topic_categories': topic_categories,
                            'subscriber_count': subscriber_count,
                            'view_count': view_count,
                            'video_count': video_count
                        })
                    except Exception as item_exc:
                        logger.warning(f"Failed to process channel payload: {item_exc}")
                        continue

            except HttpError as e:
                logger.error(f"YouTube API error fetching channel details: {e}")
                if e.resp.status == 403:
                    raise Exception("YouTube API quota exceeded or invalid API key")
                continue
            except Exception as exc:
                logger.error(f"Unexpected error fetching channel details: {exc}")
                continue

        return channel_data_list
    
    def get_video_details(self, video_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get detailed information for video IDs.
        
        Args:
            video_ids: List of YouTube video IDs (max 50 per request)
        
        Returns:
            List of video data dictionaries
        """
        if not video_ids:
            return []
        
        videos_data = []
        
        # YouTube API allows max 50 IDs per request
        batch_size = 50
        for i in range(0, len(video_ids), batch_size):
            batch = video_ids[i:i + batch_size]
            
            try:
                logger.info(f"Fetching details for {len(batch)} videos (batch {i//batch_size + 1})")
                
                videos_request = self.youtube.videos().list(
                    part='snippet,contentDetails,statistics',
                    id=','.join(batch)
                )
                
                videos_response = videos_request.execute()
                
                # Track quota usage (videos.list costs 1 unit per video)
                self.quota_used += len(batch)
                
                # Process each video
                for item in videos_response.get('items', []):
                    try:
                        snippet = item.get('snippet', {})
                        statistics = item.get('statistics', {})
                        content_details = item.get('contentDetails', {})
                        
                        video_data = {
                            'video_id': item['id'],
                            'channel_id': snippet.get('channelId', ''),
                            'title': snippet.get('title', ''),
                            'description': snippet.get('description', ''),
                            'channel_title': snippet.get('channelTitle', ''),
                            'tags': snippet.get('tags', []),
                            'category': snippet.get('categoryId'),
                            'duration': content_details.get('duration'),
                            'published_at': self._parse_datetime(snippet.get('publishedAt')),
                            'view_count': int(statistics.get('viewCount', 0)),
                            'like_count': int(statistics.get('likeCount', 0)),
                            'comment_count': int(statistics.get('commentCount', 0)),
                            'thumbnail_url': snippet.get('thumbnails', {}).get('high', {}).get('url', '')
                        }
                        
                        # Fetch channel statistics for each channel (cached per batch)
                        channel_id = video_data['channel_id']
                        if channel_id:
                            channel_stats = self.get_channel_statistics(channel_id)
                            try:
                                video_data['channel_subscriber_count'] = (
                                    int(channel_stats.get('subscriberCount')) if channel_stats.get('subscriberCount') is not None else None
                                )
                            except (ValueError, TypeError):
                                video_data['channel_subscriber_count'] = None
                            try:
                                video_data['channel_view_count'] = (
                                    int(channel_stats.get('viewCount')) if channel_stats.get('viewCount') is not None else None
                                )
                            except (ValueError, TypeError):
                                video_data['channel_view_count'] = None
                        else:
                            video_data['channel_subscriber_count'] = None
                            video_data['channel_view_count'] = None
                        
                        videos_data.append(video_data)
                        
                    except Exception as e:
                        logger.error(f"Error processing video {item.get('id')}: {e}")
                        continue
                
                logger.info(f"Successfully processed {len(videos_data)} videos")
                
            except HttpError as e:
                logger.error(f"YouTube API error fetching video details: {e}")
                if e.resp.status == 403:
                    raise Exception("YouTube API quota exceeded or invalid API key")
                continue
            except Exception as e:
                logger.error(f"Unexpected error fetching video details: {e}")
                continue
        
        return videos_data
    
    def fetch_videos_for_campaign(
        self,
        db: Session,
        campaign_id: str,
        max_results: int = 50,
        language: str = "en",
        region: str = "US",
        published_after: Optional[datetime] = None,
        published_before: Optional[datetime] = None,
        order: str = "relevance",
        video_duration: Optional[str] = None,
        video_definition: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch YouTube videos for a campaign using its keywords.
        
        Args:
            db: Database session
            campaign_id: Campaign UUID
            max_results: Maximum videos to fetch
            language: Language code
            region: Region code
            published_after: Filter videos after date
            published_before: Filter videos before date
            order: Sort order
        
        Returns:
            Dictionary with:
                - videos: List of newly added video ORM objects
                - new_videos: Count of newly added videos
                - duplicate_videos: Count of duplicates skipped
                - total_videos: Total videos stored for campaign
                - quota_used: API quota consumed
        """
        # Reset quota counter
        self.quota_used = 0
        
        # Get campaign keywords
        keywords = db.query(Keyword).filter(
            Keyword.campaign_id == campaign_id,
            Keyword.status == KeywordStatus.ACTIVE
        ).order_by(Keyword.relevance_score.desc()).all()
        
        if not keywords:
            raise ValueError("No active keywords found for campaign")
        
        logger.info(f"Fetching videos for campaign {campaign_id} with {len(keywords)} active keywords")
        
        selected_keywords, selection_summary = self._select_keywords_for_rotation(
            keywords,
            max_keyword_budget=min(len(keywords), 20),
            weight_map=KEYWORD_TYPE_WEIGHTS
        )
        logger.info(
            "Keyword selection mix: %s",
            ", ".join(f"{kw_type.value}:{count}" for kw_type, count in selection_summary.items())
        )
        
        keyword_texts = [kw.keyword for kw in selected_keywords]
        
        # Calculate videos per keyword
        max_per_keyword = max(1, max_results // len(keyword_texts))
        
        # Search for videos
        video_ids, keyword_hits = self.search_videos(
            keywords=keyword_texts,
            max_results_per_keyword=max_per_keyword,
            language=language,
            region=region,
            published_after=published_after,
            published_before=published_before,
            order=order,
            video_duration=video_duration,
            video_definition=video_definition
        )
        
        if not video_ids:
            logger.warning("No videos found for the given keywords")
            total_videos = db.query(YouTubeVideo).filter(
                YouTubeVideo.campaign_id == campaign_id
            ).count()
            return {
                'videos': [],
                'new_videos': 0,
                'duplicate_videos': 0,
                'total_videos': total_videos,
                'quota_used': self.quota_used
            }
        
        # Get video details
        videos_data = self.get_video_details(video_ids)
        
        # Save to database
        new_videos = []
        duplicate_count = 0
        
        for video_data in videos_data:
            try:
                # Check if video already exists
                existing = db.query(YouTubeVideo).filter(
                    YouTubeVideo.video_id == video_data['video_id']
                ).first()
                
                if existing:
                    duplicate_count += 1
                    continue
                
                # Create new video record
                youtube_video = YouTubeVideo(
                    campaign_id=campaign_id,
                    **video_data
                )
                
                db.add(youtube_video)
                new_videos.append(youtube_video)
                
            except Exception as e:
                logger.error(f"Error saving video {video_data.get('video_id')}: {e}")
                continue
        
        # Update keyword metadata prior to commit
        now = datetime.utcnow()
        for kw in selected_keywords:
            hits = keyword_hits.get(kw.keyword, [])
            unique_hits = len(set(hits))
            kw.last_fetched_at = now
            kw.fetch_count = (kw.fetch_count or 0) + 1
            kw.total_results = (kw.total_results or 0) + unique_hits
        
        # Commit all new videos and keyword updates
        try:
            db.commit()
            logger.info(f"✅ Saved {len(new_videos)} new videos, skipped {duplicate_count} duplicates")
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Failed to save videos to database: {e}")
            raise Exception(f"Database error: {str(e)}")
        
        # Refresh objects to get IDs
        for video in new_videos:
            db.refresh(video)
        
        total_videos = db.query(YouTubeVideo).filter(
            YouTubeVideo.campaign_id == campaign_id
        ).count()
        
        return {
            'videos': new_videos,
            'new_videos': len(new_videos),
            'duplicate_videos': duplicate_count,
            'total_videos': total_videos,
            'quota_used': self.quota_used
        }

    def fetch_channels_for_campaign(
        self,
        db: Session,
        campaign_id: str,
        max_results: int = 25,
        language: str = "en",
        region: str = "US",
        order: str = "relevance"
    ) -> Dict[str, Any]:
        """
        Fetch YouTube channels for a campaign using its keywords.

        Args:
            db: Database session.
            campaign_id: Campaign UUID.
            max_results: Maximum channels to fetch across all keywords.
            language: Language bias.
            region: Region code.
            order: Sort order.

        Returns:
            Dictionary describing persistence outcome.
        """
        self.quota_used = 0

        keywords = db.query(Keyword).filter(
            Keyword.campaign_id == campaign_id,
            Keyword.status == KeywordStatus.ACTIVE
        ).order_by(Keyword.relevance_score.desc()).all()

        if not keywords:
            raise ValueError("No active keywords found for campaign")

        selected_keywords, selection_summary = self._select_keywords_for_rotation(
            keywords,
            max_keyword_budget=min(len(keywords), 20),
            weight_map=KEYWORD_TYPE_WEIGHTS
        )
        logger.info(
            "Channel keyword selection mix: %s",
            ", ".join(f"{kw_type.value}:{count}" for kw_type, count in selection_summary.items())
        )

        keyword_texts = [kw.keyword for kw in selected_keywords]
        max_per_keyword = max(1, max_results // len(keyword_texts))

        channel_ids, _keyword_hits = self.search_channels(
            keywords=keyword_texts,
            max_results_per_keyword=max_per_keyword,
            language=language,
            region=region,
            order=order
        )

        if not channel_ids:
            total_channels = db.query(YouTubeChannel).filter(
                YouTubeChannel.campaign_id == campaign_id
            ).count()
            return {
                'channels': [],
                'new_channels': 0,
                'duplicate_channels': 0,
                'total_channels': total_channels,
                'quota_used': self.quota_used
            }

        channels_data = self.get_channel_details(channel_ids)
        new_channels: List[YouTubeChannel] = []
        duplicate_count = 0

        existing_channels: Dict[str, YouTubeChannel] = {}
        channel_ids_to_check = [data['channel_id'] for data in channels_data if data.get('channel_id')]
        if channel_ids_to_check:
            existing_channels = {
                ch.channel_id: ch
                for ch in db.query(YouTubeChannel).filter(
                    YouTubeChannel.channel_id.in_(channel_ids_to_check)
                ).all()
            }

        for channel_data in channels_data:
            channel_id = channel_data.get('channel_id')
            if not channel_id:
                continue

            if channel_id in existing_channels:
                duplicate_count += 1
                continue

            youtube_channel = YouTubeChannel(
                campaign_id=campaign_id,
                **channel_data
            )
            db.add(youtube_channel)
            new_channels.append(youtube_channel)

        try:
            db.commit()
            logger.info(f"✅ Saved {len(new_channels)} new channels, skipped {duplicate_count} duplicates")
        except Exception as exc:
            db.rollback()
            logger.error(f"❌ Failed to save channels: {exc}")
            raise Exception(f"Database error: {str(exc)}")

        for channel in new_channels:
            db.refresh(channel)

        total_channels = db.query(YouTubeChannel).filter(
            YouTubeChannel.campaign_id == campaign_id
        ).count()

        return {
            'channels': new_channels,
            'new_channels': len(new_channels),
            'duplicate_channels': duplicate_count,
            'total_channels': total_channels,
            'quota_used': self.quota_used
        }
    
    def get_campaign_videos(
        self,
        db: Session,
        campaign_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[YouTubeVideo]:
        """
        Retrieve videos for a campaign from database.
        
        Args:
            db: Database session
            campaign_id: Campaign UUID
            limit: Maximum videos to return
            offset: Number of videos to skip
        
        Returns:
            List of YouTubeVideo objects
        """
        videos = db.query(YouTubeVideo).filter(
            YouTubeVideo.campaign_id == campaign_id
        ).order_by(
            YouTubeVideo.view_count.desc()
        ).limit(limit).offset(offset).all()
        
        return videos

    def get_campaign_channels(
        self,
        db: Session,
        campaign_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[YouTubeChannel]:
        """
        Retrieve stored channels for a campaign.

        Args:
            db: Database session.
            campaign_id: Campaign UUID.
            limit: Record limit.
            offset: Pagination offset.

        Returns:
            List of YouTubeChannel objects.
        """
        channels = db.query(YouTubeChannel).filter(
            YouTubeChannel.campaign_id == campaign_id
        ).order_by(
            YouTubeChannel.subscriber_count.desc().nullslast(),
            YouTubeChannel.view_count.desc().nullslast()
        ).limit(limit).offset(offset).all()

        return channels
    
    def get_video_metadata(self, video_id: str) -> Dict[str, Any]:
        """Fetch snippet, statistics, and content details for a video."""
        try:
            request = self.youtube.videos().list(
                part='snippet,contentDetails,statistics',
                id=video_id
            )
            response = request.execute()
            self.quota_used += 1
            items = response.get('items', [])
            if not items:
                raise ValueError(f"No metadata found for video {video_id}")
            item = items[0]
            snippet = item.get('snippet', {})
            stats = item.get('statistics', {})
            details = item.get('contentDetails', {})
            return {
                'title': snippet.get('title'),
                'description': snippet.get('description'),
                'tags': snippet.get('tags', []),
                'channel_title': snippet.get('channelTitle'),
                'published_at': snippet.get('publishedAt'),
                'view_count': int(stats.get('viewCount', 0) or 0),
                'like_count': int(stats.get('likeCount', 0) or 0),
                'comment_count': int(stats.get('commentCount', 0) or 0),
                'duration': details.get('duration'),
                'category_id': snippet.get('categoryId'),
                'thumbnails': snippet.get('thumbnails', {})
            }
        except Exception as exc:
            logger.error(f"Failed to fetch metadata for {video_id}: {exc}")
            raise
    
    def get_video_transcript(
        self,
        video_id: str,
        languages: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Retrieve transcript text for a video using YouTubeTranscriptApi."""
        if languages is not None and len(languages) == 0:
            return {'text': '', 'language': None}
        preferred_languages = languages or ['en', 'en-US']
        transcript_text = ""
        selected_language = None
        
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript_obj = None
            
            try:
                transcript_obj = transcript_list.find_manually_created_transcript(preferred_languages)
            except NoTranscriptFound:
                pass
            
            if not transcript_obj:
                try:
                    transcript_obj = transcript_list.find_generated_transcript(preferred_languages)
                except NoTranscriptFound:
                    pass
            
            if not transcript_obj:
                for transcript in transcript_list:
                    transcript_obj = transcript
                    break
            
            if transcript_obj:
                transcript = transcript_obj.fetch()
                transcript_text = " ".join(
                    segment.get('text', '')
                    for segment in transcript
                    if segment.get('text')
                )
                selected_language = transcript_obj.language_code
            else:
                logger.warning(f"No transcript sources available for {video_id}")
        
        except (TranscriptsDisabled, NoTranscriptFound, CouldNotRetrieveTranscript) as exc:
            logger.warning(f"Transcript unavailable for {video_id}: {exc}")
        except Exception as exc:
            logger.warning(f"Transcript fetch error for {video_id}: {exc}")
        
        return {
            'text': transcript_text,
            'language': selected_language
        }
    
    def get_video_information(
        self,
        video_id: str,
        languages: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Fetch metadata + transcript for deeper scoring analysis."""
        try:
            metadata = self.get_video_metadata(video_id)
        except Exception:
            metadata = {}
        transcript = self.get_video_transcript(video_id, languages=languages)
        return {
            'metadata': metadata,
            'transcript': transcript.get('text', ''),
            'transcript_language': transcript.get('language')
        }
    
    def get_campaign_video_stats(
        self,
        db: Session,
        campaign_id: str
    ) -> Dict[str, Any]:
        """
        Calculate aggregate statistics for campaign videos.
        
        Args:
            db: Database session
            campaign_id: Campaign UUID
        
        Returns:
            Dictionary with totals and averages used by the dashboard.
        """
        stats = db.query(
            func.count(YouTubeVideo.id).label("total_videos"),
            func.coalesce(func.sum(YouTubeVideo.view_count), 0).label("total_views"),
            func.coalesce(func.sum(YouTubeVideo.like_count), 0).label("total_likes"),
            func.coalesce(func.sum(YouTubeVideo.comment_count), 0).label("total_comments")
        ).filter(
            YouTubeVideo.campaign_id == campaign_id
        ).one()
        
        unique_channels = db.query(
            func.count(func.distinct(YouTubeVideo.channel_id))
        ).filter(
            YouTubeVideo.campaign_id == campaign_id
        ).scalar() or 0
        
        total_videos = stats.total_videos or 0
        avg_views = (stats.total_views // total_videos) if total_videos else 0
        avg_likes = (stats.total_likes // total_videos) if total_videos else 0
        avg_comments = (stats.total_comments // total_videos) if total_videos else 0

        return {
            "campaign_id": campaign_id,
            "total_videos": total_videos,
            "total_views": int(stats.total_views or 0),
            "total_likes": int(stats.total_likes or 0),
            "total_comments": int(stats.total_comments or 0),
            "avg_views": int(avg_views),
            "avg_likes": int(avg_likes),
            "avg_comments": int(avg_comments),
            "unique_channels": int(unique_channels)
        }
    
    def _parse_datetime(self, date_string: Optional[str]) -> Optional[datetime]:
        """
        Parse ISO datetime string from YouTube API.
        
        Args:
            date_string: ISO format datetime string
        
        Returns:
            datetime object or None
        """
        if not date_string:
            return None
        
        try:
            # Remove 'Z' and parse
            return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except Exception as e:
            logger.error(f"Error parsing datetime '{date_string}': {e}")
            return None
    
    def test_connection(self) -> bool:
        """
        Test YouTube API connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Simple test request
            request = self.youtube.videos().list(
                part='snippet',
                id='dQw4w9WgXcQ',  # Rick Roll video ID (always exists)
                maxResults=1
            )
            response = request.execute()
            
            if response.get('items'):
                logger.info("✅ YouTube API connection test successful")
                return True
            else:
                logger.warning("⚠️  YouTube API connection test returned no results")
                return False
                
        except Exception as e:
            logger.error(f"❌ YouTube API connection test failed: {e}")
            return False


# Global service instance
youtube_service = YouTubeService()
