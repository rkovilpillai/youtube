import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { VideoAPI } from "../api/client";
import PageHeader from "../components/PageHeader";
import SectionCard from "../components/SectionCard";
import { useCampaign } from "../context/CampaignContext";
import { VideoFetchRequest, VideoResponseItem } from "../types/video";
import { ChannelResponseItem } from "../types/channel";
import { languageOptions, marketOptions } from "../data/campaignOptions";
const languages = languageOptions;
const regions = marketOptions;
const orders = ["relevance", "date", "viewCount", "rating"];

const VideoFetchPage = () => {
  const { currentCampaign } = useCampaign();
  const [activeTab, setActiveTab] = useState<"videos" | "channels">("videos");
  const [filters, setFilters] = useState<VideoFetchRequest>(() => ({
    campaign_id: currentCampaign?.id ?? "",
    max_results: 50,
    language: currentCampaign?.primary_language ?? "en",
    region: currentCampaign?.primary_market ?? "US",
    order: "relevance",
    include_channels: true,
    channel_max_results: 25,
  }));
  const [useDateFilter, setUseDateFilter] = useState(false);
  const [daysBack, setDaysBack] = useState(30);

  useEffect(() => {
    if (!currentCampaign) {
      return;
    }
    setFilters((prev) => ({
      ...prev,
      campaign_id: currentCampaign.id,
      language: currentCampaign.primary_language ?? prev.language ?? "en",
      region: currentCampaign.primary_market ?? prev.region ?? "US",
      include_channels: prev.include_channels ?? true,
      channel_max_results: prev.channel_max_results ?? 25,
    }));
  }, [currentCampaign]);

  const videosQuery = useQuery({
    queryKey: ["videos", currentCampaign?.id],
    queryFn: () => VideoAPI.listCampaignVideos(currentCampaign!.id),
    enabled: Boolean(currentCampaign?.id),
  });
  const channelsQuery = useQuery({
    queryKey: ["channels", currentCampaign?.id],
    queryFn: () => VideoAPI.listCampaignChannels(currentCampaign!.id),
    enabled: Boolean(currentCampaign?.id),
  });

  const fetchMutation = useMutation({
    mutationFn: () =>
      VideoAPI.fetchVideos({
        ...filters,
        campaign_id: currentCampaign!.id,
        published_after: useDateFilter
          ? new Date(Date.now() - daysBack * 24 * 60 * 60 * 1000).toISOString()
          : undefined,
      }),
    onSuccess: () => {
      videosQuery.refetch();
      if (filters.include_channels !== false) {
        channelsQuery.refetch();
      }
    },
  });

  const testConnectionMutation = useMutation({
    mutationFn: () => VideoAPI.testConnection(),
  });

  const onChangeFilter = <K extends keyof VideoFetchRequest>(key: K, value: VideoFetchRequest[K]) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

  const videos: VideoResponseItem[] = videosQuery.data?.data.videos ?? [];
  const channels: ChannelResponseItem[] = channelsQuery.data?.data.channels ?? [];
  const formatNumber = (value?: number | null) =>
    value === undefined || value === null ? "–" : value.toLocaleString();
  const buildChannelUrl = (channel: ChannelResponseItem) => {
    if (channel.custom_url) {
      if (channel.custom_url.startsWith("http")) {
        return channel.custom_url;
      }
      const trimmed = channel.custom_url.replace(/^\/+/, "");
      return `https://www.youtube.com/${trimmed}`;
    }
    return `https://www.youtube.com/channel/${channel.channel_id}`;
  };

  if (!currentCampaign) {
    return (
      <div className="page">
        <PageHeader title="Video Fetch" />
        <SectionCard
          title="No campaign selected"
          description="Select a campaign in the Campaign Setup page before fetching videos."
        >
          <p>Choose a campaign to access YouTube filters and fetch controls.</p>
        </SectionCard>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title="Video Fetch"
        subtitle={`Use campaign keywords to discover YouTube inventory for ${currentCampaign.name}.`}
        actions={
          <button
            className="secondary"
            onClick={() => testConnectionMutation.mutateAsync()}
            disabled={testConnectionMutation.isPending}
          >
            {testConnectionMutation.isPending ? "Testing…" : "Test Connection"}
          </button>
        }
      />

      <div className="view-toggle">
        <button
          className={`chip ${activeTab === "videos" ? "selected" : ""}`}
          onClick={() => setActiveTab("videos")}
        >
          Video Fetch
        </button>
        <button
          className={`chip ${activeTab === "channels" ? "selected" : ""}`}
          onClick={() => setActiveTab("channels")}
        >
          Channel Discovery
        </button>
      </div>

      <div className="grid-two">
        <SectionCard
          title="Unified Discovery Configuration"
          description="Tune parameters once to fetch videos and, optionally, contextual channels."
        >
          <form
            className="form-grid"
            onSubmit={(e) => {
              e.preventDefault();
              fetchMutation.mutate();
            }}
          >
            <label>
              <span>Video Max Results</span>
              <input
                type="number"
                min={1}
                max={200}
                value={filters.max_results}
                onChange={(e) => onChangeFilter("max_results", Number(e.target.value))}
              />
            </label>
            <label>
              <span>Language</span>
              <select
                value={filters.language}
                onChange={(e) => onChangeFilter("language", e.target.value)}
              >
                {languages.map(({ value, label }) => (
                  <option key={value} value={value}>
                    {label} ({value.toUpperCase()})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Region</span>
              <select
                value={filters.region}
                onChange={(e) => onChangeFilter("region", e.target.value)}
              >
                {regions.map(({ value, label }) => (
                  <option key={value} value={value}>
                    {label} ({value})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Order</span>
              <select
                value={filters.order}
                onChange={(e) => onChangeFilter("order", e.target.value)}
              >
                {orders.map((order) => (
                  <option key={order} value={order}>
                    {order}
                  </option>
                ))}
              </select>
            </label>

            <div className="span-two">
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={filters.include_channels !== false}
                  onChange={(e) => onChangeFilter("include_channels", e.target.checked)}
                />
                Include Channel Discovery
              </label>
            </div>

            {filters.include_channels !== false && (
              <label>
                <span>Channel Max Results</span>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={filters.channel_max_results ?? 25}
                  onChange={(e) => onChangeFilter("channel_max_results", Number(e.target.value))}
                />
              </label>
            )}

            <div className="span-two">
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={useDateFilter}
                  onChange={(e) => setUseDateFilter(e.target.checked)}
                />
                Use Date Filter
              </label>
              {useDateFilter && (
                <label>
                  <span>Days Back</span>
                  <input
                    type="number"
                    min={1}
                    max={365}
                    value={daysBack}
                    onChange={(e) => setDaysBack(Number(e.target.value))}
                  />
                </label>
              )}
            </div>

            <div className="span-two button-row">
              <button className="primary" type="submit" disabled={fetchMutation.isPending}>
                {fetchMutation.isPending ? "Fetching…" : "Fetch Inventory"}
              </button>
            </div>
          </form>
        </SectionCard>

        {fetchMutation.data && fetchMutation.data.success && (
          <>
            <SectionCard
              title="Video Fetch Summary"
              description="Recent job metrics stored by the backend."
            >
              <div className="metrics-grid">
                <div>
                  <h4>New Videos</h4>
                  <p>{fetchMutation.data.data.new_videos}</p>
                </div>
                <div>
                  <h4>Duplicates</h4>
                  <p>{fetchMutation.data.data.duplicate_videos}</p>
                </div>
                <div>
                  <h4>Total Stored</h4>
                  <p>{fetchMutation.data.data.total_videos}</p>
                </div>
                <div>
                  <h4>Video Quota Used</h4>
                  <p>{fetchMutation.data.data.video_quota_used ?? fetchMutation.data.data.quota_used}</p>
                </div>
              </div>
            </SectionCard>
            {filters.include_channels !== false && (
              <SectionCard
                title="Channel Discovery Summary"
                description="Channel metrics captured during this fetch."
              >
                <div className="metrics-grid">
                  <div>
                    <h4>New Channels</h4>
                    <p>{fetchMutation.data.data.new_channels ?? 0}</p>
                  </div>
                  <div>
                    <h4>Duplicates</h4>
                    <p>{fetchMutation.data.data.duplicate_channels ?? 0}</p>
                  </div>
                  <div>
                    <h4>Total Stored</h4>
                    <p>{fetchMutation.data.data.total_channels ?? 0}</p>
                  </div>
                  <div>
                    <h4>Channel Quota Used</h4>
                    <p>{fetchMutation.data.data.channel_quota_used ?? 0}</p>
                  </div>
                </div>
              </SectionCard>
            )}
          </>
        )}
      </div>

      <SectionCard
        title={activeTab === "videos" ? "Fetched Videos" : "Discovered Channels"}
        description={
          activeTab === "videos"
            ? "Inspect campaign inventory and open videos on YouTube."
            : "Explore contextual creators surfaced for this campaign."
        }
      >
        {activeTab === "videos" ? (
          videosQuery.isLoading ? (
            <p>Loading videos...</p>
          ) : videos.length === 0 ? (
            <p>No videos fetched yet. Run a fetch to populate this list.</p>
          ) : (
            <>
              <div className="view-toggle">
                <button
                  className={`chip ${viewMode === "grid" ? "selected" : ""}`}
                  onClick={() => setViewMode("grid")}
                >
                  Grid View
                </button>
                <button
                  className={`chip ${viewMode === "list" ? "selected" : ""}`}
                  onClick={() => setViewMode("list")}
                >
                  List View
                </button>
              </div>
              {viewMode === "grid" ? (
                <div className="video-grid">
                  {videos.map((video) => (
                    <article key={video.id} className="video-card">
                      {video.thumbnail_url && (
                        <img src={video.thumbnail_url} alt={video.title} className="thumbnail" />
                      )}
                      <div className="video-body">
                        <h4>{video.title}</h4>
                        <p className="muted">{video.channel_title ?? "Unknown channel"}</p>
                        {video.description && (
                          <p className="description">{video.description}</p>
                        )}
                        <div className="metrics-line">
                          <span>Views {(video.view_count ?? 0).toLocaleString()}</span>
                          <span>Likes {(video.like_count ?? 0).toLocaleString()}</span>
                          <span>Comments {(video.comment_count ?? 0).toLocaleString()}</span>
                        </div>
                        <div className="actions">
                          <a
                            className="secondary"
                            target="_blank"
                            rel="noreferrer"
                            href={`https://www.youtube.com/watch?v=${video.video_id}`}
                          >
                            Watch
                          </a>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <table className="video-table">
                  <thead>
                    <tr>
                      <th> </th>
                      <th>Title</th>
                      <th>Channel</th>
                      <th>Views</th>
                      <th>Likes</th>
                      <th>Comments</th>
                      <th>Published</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {videos.map((video) => (
                      <tr key={video.id}>
                        <td className="thumb-cell">
                          {video.thumbnail_url && (
                            <img src={video.thumbnail_url} alt={video.title} className="thumb-mini" />
                          )}
                        </td>
                        <td>{video.title}</td>
                        <td>{video.channel_title ?? "Unknown"}</td>
                        <td>{(video.view_count ?? 0).toLocaleString()}</td>
                        <td>{(video.like_count ?? 0).toLocaleString()}</td>
                        <td>{(video.comment_count ?? 0).toLocaleString()}</td>
                        <td>
                          {video.published_at
                            ? new Date(video.published_at).toLocaleDateString()
                            : "–"}
                        </td>
                        <td>
                          <a
                            className="secondary"
                            href={`https://www.youtube.com/watch?v=${video.video_id}`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Watch
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )
        ) : channelsQuery.isLoading ? (
          <p>Loading channels...</p>
        ) : channels.length === 0 ? (
          <p>No channels stored yet. Run a discovery to populate this list.</p>
        ) : (
          <div className="video-grid">
            {channels.map((channel) => (
              <article key={channel.id} className="video-card channel-card">
                {channel.thumbnail_url && (
                  <img src={channel.thumbnail_url} alt={channel.title} className="thumbnail" />
                )}
                <div className="video-body">
                  <h4>{channel.title}</h4>
                  <p className="muted">
                    {channel.country ? `Market: ${channel.country.toUpperCase()}` : "Global"}
                  </p>
                  {channel.description && <p className="description">{channel.description}</p>}
                  <div className="metrics-line">
                    <span>Subs {formatNumber(channel.subscriber_count)}</span>
                    <span>Views {formatNumber(channel.view_count)}</span>
                    <span>Videos {formatNumber(channel.video_count)}</span>
                  </div>
                  {channel.topic_categories && channel.topic_categories.length > 0 && (
                    <div className="chip-row">
                      {channel.topic_categories.slice(0, 3).map((topic) => {
                        const label =
                          topic && topic.includes("/")
                            ? topic.substring(topic.lastIndexOf("/") + 1)
                            : topic;
                        return (
                          <span key={topic} className="chip muted">
                            {label}
                          </span>
                        );
                      })}
                    </div>
                  )}
                  <div className="actions">
                    <a
                      className="secondary"
                      target="_blank"
                      rel="noreferrer"
                      href={buildChannelUrl(channel)}
                    >
                      View Channel
                    </a>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
};

export default VideoFetchPage;
