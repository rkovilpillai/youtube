export interface ChannelFetchRequest {
  campaign_id: string;
  max_results: number;
  language: string;
  region: string;
  order: string;
}

export interface ChannelResponseItem {
  id: string;
  campaign_id: string;
  channel_id: string;
  title: string;
  description?: string;
  custom_url?: string;
  country?: string;
  published_at?: string;
  thumbnail_url?: string;
  keywords?: string[] | null;
  topic_categories?: string[] | null;
  subscriber_count?: number | null;
  view_count?: number | null;
  video_count?: number | null;
}

export interface ChannelFetchResponse {
  success: boolean;
  data: {
    campaign_id: string;
    channels: ChannelResponseItem[];
    total_channels: number;
    new_channels: number;
    duplicate_channels: number;
    quota_used: number;
  };
}

export interface CampaignChannelsResponse {
  success: boolean;
  data: {
    campaign_id: string;
    channels: ChannelResponseItem[];
    total_channels: number;
    returned_channels: number;
    skip?: number;
    limit?: number;
  };
}
