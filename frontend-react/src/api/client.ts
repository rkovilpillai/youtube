import axios from "axios";

import {
  Campaign,
  CampaignCreateResponse,
  CampaignListResponse,
} from "../types/campaign";
import {
  KeywordListResponse,
  KeywordType,
  KeywordGenerateRequest,
} from "../types/keyword";
import {
  VideoFetchRequest,
  VideoFetchResponse,
  CampaignVideosResponse,
} from "../types/video";
import {
  ScoreCampaignResponse,
  ScoreVideoRequest,
  BatchScoreRequest,
  TranscriptResponse,
  BatchScoreResponse,
} from "../types/scoring";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const apiClient = axios.create({
  baseURL,
  headers: {
    "Content-Type": "application/json",
  },
});

export const CampaignAPI = {
  async list(params: { skip?: number; limit?: number } = {}) {
    const response = await apiClient.get<CampaignListResponse>("/api/campaign", { params });
    return response.data;
  },
  async create(payload: Record<string, unknown>) {
    const response = await apiClient.post<CampaignCreateResponse>("/api/campaign/create", payload);
    return response.data;
  },
  async get(campaignId: string) {
    const response = await apiClient.get<{ success: boolean; data: Campaign }>(
      `/api/campaign/${campaignId}`
    );
    return response.data;
  },
};

export const KeywordAPI = {
  async list(campaignId: string, params: { keyword_type?: KeywordType; status_filter?: string } = {}) {
    const response = await apiClient.get<KeywordListResponse>(
      `/api/keywords/${campaignId}`,
      { params }
    );
    return response.data;
  },
  async generate(payload: KeywordGenerateRequest) {
    const response = await apiClient.post("/api/keywords/generate", payload);
    return response.data;
  },
  async addManualKeyword(payload: {
    campaign_id: string;
    keyword: string;
    keyword_type: KeywordType;
    relevance_score: number;
  }) {
    const response = await apiClient.post("/api/keywords/manual-add", {
      ...payload,
      source: "manual",
    });
    return response.data;
  },
};

export const VideoAPI = {
  async fetchVideos(payload: VideoFetchRequest) {
    const response = await apiClient.post<VideoFetchResponse>('/api/youtube/fetch', payload);
    return response.data;
  },
  async listCampaignVideos(campaignId: string, params: { skip?: number; limit?: number } = {}) {
    const response = await apiClient.get<CampaignVideosResponse>(`/api/youtube/videos/${campaignId}`, { params });
    return response.data;
  },
  async testConnection() {
    const response = await apiClient.get('/api/youtube/test-connection');
    return response.data;
  },
  async deleteCampaignVideos(campaignId: string) {
    const response = await apiClient.delete(`/api/youtube/videos/${campaignId}`);
    return response.data;
  },
};

export const ScoringAPI = {
  async scoreVideo(payload: ScoreVideoRequest) {
    const response = await apiClient.post<{ success: boolean; data: VideoScore }>(
      "/api/scoring/contextual-score",
      payload
    );
    return response.data;
  },
  async batchScore(payload: BatchScoreRequest) {
    const response = await apiClient.post<BatchScoreResponse>("/api/scoring/batch", payload);
    return response.data;
  },
  async campaignScores(campaignId: string) {
    const response = await apiClient.get<ScoreCampaignResponse>(
      `/api/scoring/campaign/${campaignId}`
    );
    return response.data;
  },
  async transcript(campaignId: string, videoId: string) {
    const response = await apiClient.get<TranscriptResponse>(
      `/api/transcript/${campaignId}/${videoId}`
    );
    return response.data;
  },
};
