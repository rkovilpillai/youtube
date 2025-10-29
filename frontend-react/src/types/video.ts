export interface VideoFetchRequest {
  campaign_id: string;
  max_results: number;
  language: string;
  region: string;
  published_after?: string | null;
  published_before?: string | null;
  order: string;
}

export interface VideoResponseItem {
  id: string;
  campaign_id: string;
  video_id: string;
  channel_id: string;
  title: string;
  description?: string;
  channel_title?: string;
  view_count: number;
  like_count: number;
  comment_count: number;
  channel_view_count?: number | null;
  channel_subscriber_count?: number | null;
  thumbnail_url?: string;
  published_at?: string;
}

export interface VideoFetchResponse {
  success: boolean;
  data: {
    campaign_id: string;
    videos: VideoResponseItem[];
    total_videos: number;
    new_videos: number;
    duplicate_videos: number;
    quota_used: number;
  };
}

export interface CampaignVideosResponse {
  success: boolean;
  data: {
    campaign_id: string;
    videos: VideoResponseItem[];
    total_videos: number;
    returned_videos: number;
  };
}
