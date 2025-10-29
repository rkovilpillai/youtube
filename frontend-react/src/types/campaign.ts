export interface Campaign {
  id: string;
  name: string;
  brand_name: string;
  brand_url?: string | null;
  product_category: string;
  campaign_goal: string;
  campaign_definition: string;
  brand_context_text?: string | null;
  audience_intent?: string | null;
  audience_persona?: string | null;
  tone_profile?: string | null;
  emotion_guidance?: string[] | null;
  interest_guidance?: string[] | null;
  guardrail_terms?: string[] | null;
  inspiration_links?: string[] | null;
  primary_language?: string | null;
  primary_market?: string | null;
  avg_view_count?: number | null;
  avg_like_count?: number | null;
  avg_comment_count?: number | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface CampaignListResponse {
  success: boolean;
  data: {
    campaigns: Campaign[];
    total: number;
    skip: number;
    limit: number;
  };
}

export interface CampaignCreateResponse {
  success: boolean;
  data: Campaign;
}
