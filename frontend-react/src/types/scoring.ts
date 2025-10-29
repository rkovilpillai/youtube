export interface VideoScore {
  id: string;
  campaign_id: string;
  video_record_id: string;
  video_id: string;
  channel_id: string;
  video_url: string;
  channel_url: string;
  semantic_similarity_score: number;
  intent_score: number;
  interest_score: number;
  emotion_score: number;
  contextual_score: number;
  brand_safety_status: string;
  brand_suitability: string;
  sentiment: string;
  tone: string;
  key_entities: string[];
  key_topics: string[];
  intent_type?: string;
  interest_topics?: string[];
  emotion_type?: string;
  targeting_recommendation: string;
  suggested_bid_modifier: number;
  reasoning?: string;
  scored_at: string;
}

export interface ScoreCampaignResponse {
  success: boolean;
  data: {
    campaign_id: string;
    total_scored: number;
    average_contextual_score: number;
    recommendation_breakdown: Record<string, number>;
    scores: VideoScore[];
  };
}

export interface ScoreVideoRequest {
  campaign_id: string;
  video_id: string;
  use_transcript: boolean;
}

export interface BatchScoreRequest {
  campaign_id: string;
  video_ids: string[];
  use_transcript: boolean;
}

export interface BatchScoreResponse {
  success: boolean;
  data: {
    campaign_id: string;
    processed: number;
    failed: number;
    results: Array<{ video_id: string; contextual_score?: number; brand_suitability?: string }>;
    errors: Array<{ video_id: string; error: unknown }>;
  };
}

export interface TranscriptResponse {
  success: boolean;
  data: {
    video_id: string;
    language: string | null;
    transcript: string;
  };
}
