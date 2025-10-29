export type KeywordType = "core" | "long-tail" | "related" | "intent-based";

export interface Keyword {
  id: string;
  campaign_id: string;
  keyword: string;
  keyword_type: KeywordType;
  relevance_score: number;
  source: "ai-generated" | "manual";
  status: "active" | "inactive";
  created_at: string;
}

export interface KeywordListResponse {
  success: boolean;
  data: {
    keywords: Keyword[];
    total: number;
    campaign_id: string;
  };
}

export interface KeywordGenerateRequest {
  campaign_id: string;
  num_core_keywords: number;
  num_long_tail: number;
  num_related: number;
  num_intent_based: number;
}
