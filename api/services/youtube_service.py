"""
YouTube Service - Integration with YouTube Data API v3.
Handles video fetching, metadata retrieval, and channel information.
"""
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
import logging
from collections import defaultdict

from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    CouldNotRetrieveTranscript
)

from api.config import settings
from api.models import YouTubeVideo, Keyword, KeywordStatus, KeywordType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        
        # Determine diversified keyword selection (balanced across types, prioritising low coverage and stale queries)
        max_keyword_budget = min(len(keywords), 20)
        if max_keyword_budget == 0:
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
        
        keyword_type_order = [KeywordType.CORE, KeywordType.LONG_TAIL, KeywordType.RELATED, KeywordType.INTENT_BASED]
        available_types = [kw_type for kw_type in keyword_type_order if keywords_by_type.get(kw_type)]
        if not available_types:
            # Fall back to any keyword types present
            available_types = list(keywords_by_type.keys())
        
        selected_keywords: List[Keyword] = []
        if available_types:
            base_share = max_keyword_budget // len(available_types)
            extra_slots = max_keyword_budget % len(available_types)
            used_keyword_ids = set()
            
            # Initial allocation per type
            for kw_type in available_types:
                bucket = keywords_by_type.get(kw_type, [])
                if not bucket:
                    continue
                share = base_share
                if extra_slots > 0:
                    share += 1
                    extra_slots -= 1
                take = min(share, len(bucket))
                selected_keywords.extend(bucket[:take])
                used_keyword_ids.update(kw.id for kw in bucket[:take])
            
            # Fill any remaining slots with best remaining keywords regardless of type
            if len(selected_keywords) < max_keyword_budget:
                remaining_candidates = [
                    kw for bucket in keywords_by_type.values() for kw in bucket
                    if kw.id not in used_keyword_ids
                ]
                remaining_candidates.sort(key=keyword_priority_key)
                take_count = max_keyword_budget - len(selected_keywords)
                selected_keywords.extend(remaining_candidates[:take_count])
        else:
            # Should not happen, but fallback to top keywords globally
            selected_keywords = sorted(keywords, key=keyword_priority_key)[:max_keyword_budget]
        
        if not selected_keywords:
            raise ValueError("Unable to select keywords for fetch request")
        
        selection_summary = defaultdict(int)
        for kw in selected_keywords:
            selection_summary[kw.keyword_type] += 1
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
