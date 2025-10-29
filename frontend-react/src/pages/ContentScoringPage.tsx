import { Fragment, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import PageHeader from "../components/PageHeader";
import SectionCard from "../components/SectionCard";
import { useCampaign } from "../context/CampaignContext";
import { ScoringAPI } from "../api/client";
import { ScoreCampaignResponse, VideoScore, BatchScoreResponse } from "../types/scoring";
import { VideoAPI } from "../api/client";
import { VideoResponseItem } from "../types/video";

const ContentScoringPage = () => {
  const { currentCampaign } = useCampaign();
  const [useTranscript, setUseTranscript] = useState(false);
  const [batchCount, setBatchCount] = useState(5);
  const [lastBatchSize, setLastBatchSize] = useState(0);
  const [batchResult, setBatchResult] = useState<{ processed: number; failed: number } | null>(null);

  const scoresQuery = useQuery({
    queryKey: ["scores", currentCampaign?.id],
    queryFn: () => ScoringAPI.campaignScores(currentCampaign!.id),
    enabled: Boolean(currentCampaign?.id),
  });

  const videosQuery = useQuery({
    queryKey: ["videos-for-scoring", currentCampaign?.id],
    queryFn: () => VideoAPI.listCampaignVideos(currentCampaign!.id),
    enabled: Boolean(currentCampaign?.id),
  });

  const refetchScores = scoresQuery.refetch;
  const refetchVideos = videosQuery.refetch;

  const batchScoreMutation = useMutation<BatchScoreResponse, Error, string[]>({
    mutationFn: (videoIds: string[]) =>
      ScoringAPI.batchScore({
        campaign_id: currentCampaign!.id,
        video_ids: videoIds,
        use_transcript: useTranscript,
      }),
    onMutate: (videoIds) => {
      setLastBatchSize(videoIds.length);
      setBatchResult(null);
    },
    onSuccess: (payload) => {
      setBatchResult({
        processed: payload.data.processed,
        failed: payload.data.failed,
      });
      refetchScores();
      refetchVideos();
    },
    onError: () => {
      setBatchResult({ processed: 0, failed: lastBatchSize });
    },
  });

  const scoreMutation = useMutation({
    mutationFn: (videoId: string) =>
      ScoringAPI.scoreVideo({
        campaign_id: currentCampaign!.id,
        video_id: videoId,
        use_transcript: useTranscript,
      }),
    onSuccess: () => {
      refetchScores();
      refetchVideos();
    },
  });

  const pollForProgress = batchScoreMutation.isPending;
  useEffect(() => {
    if (!pollForProgress) {
      return;
    }
    const interval = setInterval(() => {
      refetchVideos();
      refetchScores();
    }, 1500);
    return () => clearInterval(interval);
  }, [pollForProgress, refetchVideos, refetchScores]);

  const [selectedScore, setSelectedScore] = useState<VideoScore | null>(null);
  const [currentPage, setCurrentPage] = useState(0);
  const pageSize = 10;

  const videos = videosQuery.data?.data.videos ?? [];
  const scores = scoresQuery.data?.data.scores ?? [];

  const campaignAverages = useMemo(() => {
    if (!currentCampaign) return null;
    return {
      views: currentCampaign.avg_view_count ?? 0,
      likes: currentCampaign.avg_like_count ?? 0,
      comments: currentCampaign.avg_comment_count ?? 0,
    };
  }, [currentCampaign]);

  const videoLookup = useMemo(() => {
    const map = new Map<string, VideoResponseItem>();
    videos.forEach((video) => map.set(video.video_id, video));
    return map;
  }, [videos]);

  const exportCsv = (rows: string[], filename: string) => {
    if (!rows.length) return;
    const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleExportVideos = () => {
    const rows = ["video_url,video_id,contextual_score,targeting_recommendation"];
    scores.forEach((score) => {
      rows.push(
        `${score.video_url},${score.video_id},${score.contextual_score.toFixed(2)},${score.targeting_recommendation}`
      );
    });
    exportCsv(rows, `${currentCampaign!.name.replace(/[^a-z0-9_-]+/gi, "-")}_video_urls.csv`);
  };

  const handleExportChannels = () => {
    const unique = new Map<string, VideoScore>();
    scores.forEach((score) => {
      if (score.channel_url && !unique.has(score.channel_url)) {
        unique.set(score.channel_url, score);
      }
    });
    const rows = ["channel_url,channel_id,targeting_recommendation"];
    unique.forEach((score) => {
      rows.push(`${score.channel_url},${score.channel_id},${score.targeting_recommendation}`);
    });
    exportCsv(rows, `${currentCampaign!.name.replace(/[^a-z0-9_-]+/gi, "-")}_channel_urls.csv`);
  };

  const pendingVideos = useMemo(() => {
    if (!videos.length) return [];
    const scoredIds = new Set(scores.map((score) => score.video_id));
    return videos.filter((video) => !scoredIds.has(video.video_id));
  }, [videos, scores]);

  const pendingCount = pendingVideos.length;

  useEffect(() => {
    if (pendingCount > 0 && batchCount > pendingCount) {
      setBatchCount(pendingCount);
    }
  }, [pendingCount, batchCount]);


  if (!currentCampaign) {
    return (
      <div className="page">
        <PageHeader title="Content Scoring" />
        <SectionCard
          title="No campaign selected"
          description="Choose a campaign on the Campaign Setup page to access scoring tools."
        >
          <p>Select a campaign to run Liz AI scoring.</p>
        </SectionCard>
      </div>
    );
  }

  const totalPages = Math.ceil(scores.length / pageSize) || 1;
  const pageSafe = Math.min(currentPage, totalPages - 1);
  const paginatedScores = scores.slice(pageSafe * pageSize, pageSafe * pageSize + pageSize);

  useEffect(() => {
    if (currentPage > totalPages - 1) {
      setCurrentPage(Math.max(totalPages - 1, 0));
    }
  }, [totalPages, currentPage]);

  return (
    <div className="page">
      <PageHeader
        title="Content Scoring"
        subtitle="Evaluate campaign videos with Liz AI and export high-quality placements."
      />

      <div className="grid-two">
        <SectionCard
          title="Scoring Controls"
          description="Score pending videos individually or in batches."
        >
          <div className="form-grid">
            <label className="toggle">
              <input
                type="checkbox"
                checked={useTranscript}
                onChange={(e) => setUseTranscript(e.target.checked)}
              />
              Include transcript when scoring
            </label>

            <label>
              <span>Videos to score</span>
              <input
                type="number"
                min={1}
                max={Math.max(pendingCount, 1)}
                value={pendingCount === 0 ? 1 : batchCount}
                onChange={(e) => setBatchCount(Math.max(1, Math.min(Number(e.target.value), Math.max(pendingCount, 1))))}
                disabled={pendingCount === 0}
              />
            </label>

            <button
              className="primary"
              disabled={!pendingVideos.length || batchScoreMutation.isPending}
              onClick={() => {
                const slice = pendingVideos.slice(0, batchCount);
                if (slice.length) {
                  batchScoreMutation.mutate(slice.map((video) => video.video_id));
                }
              }}
            >
              {batchScoreMutation.isPending
                ? "Scoring videos…"
                : `Score next ${Math.min(batchCount, pendingCount)} videos`}
            </button>
          </div>

          {batchScoreMutation.isPending && (
            <div className="progress-card">
              <div className="progress-bar">
                <div className="progress-indeterminate" />
              </div>
              <p>Scoring {Math.min(batchCount, pendingCount)} videos with Liz AI…</p>
            </div>
          )}

          {batchResult && !batchScoreMutation.isPending && (
            <div className="result-banner">
              <strong>{batchResult.processed} processed</strong>
              {batchResult.failed > 0 && (
                <span> · {batchResult.failed} failed</span>
              )}
            </div>
          )}

          {pendingVideos.length === 0 ? (
            <p>All videos have been scored.</p>
          ) : (
            <p>{pendingVideos.length} videos awaiting scoring.</p>
          )}
        </SectionCard>

        <SectionCard
          title="Scoring Summary"
          description="Aggregate insight across scored inventory."
        >
          {scoresQuery.isLoading ? (
            <p>Loading scoring metrics...</p>
          ) : scores.length === 0 ? (
            <p>No scored videos yet. Run Liz AI scoring to populate metrics.</p>
          ) : (
            <div className="metrics-grid">
              <div>
                <h4>Total Scored</h4>
                <p>{scoresQuery.data?.data.total_scored ?? 0}</p>
              </div>
              <div>
                <h4>Average Score</h4>
                <p>{(scoresQuery.data?.data.average_contextual_score ?? 0).toFixed(2)}</p>
              </div>
              <div>
                <h4>Strong Matches</h4>
                <p>{scoresQuery.data?.data.recommendation_breakdown["strong_match"] ?? 0}</p>
              </div>
              <div>
                <h4>Moderate Matches</h4>
                <p>{scoresQuery.data?.data.recommendation_breakdown["moderate_match"] ?? 0}</p>
              </div>
            </div>
          )}
        </SectionCard>
      </div>

      <SectionCard
        title="Scored Videos"
        description="Review Liz AI output and export DV360-ready lists."
      >
        {scoresQuery.isLoading ? (
          <p>Loading scored videos...</p>
        ) : scores.length === 0 ? (
          <p>No scored videos yet. Run the scoring workflow above.</p>
        ) : (
          <div className="score-table-wrapper">
            <div className="exports-row">
              <button className="secondary" onClick={handleExportVideos}>
                Download Video URLs CSV
              </button>
              <button className="secondary" onClick={handleExportChannels}>
                Download Channel URLs CSV
              </button>
            </div>
            <table className="score-table">
              <thead>
                <tr>
                  <th>Video</th>
                  <th>Contextual</th>
                  <th>Intent / Interest / Emotion</th>
                  <th>Recommendation</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {paginatedScores.map((score) => {
                  const video = videoLookup.get(score.video_id);
                  const isSelected = selectedScore?.id === score.id;
                  return (
                    <Fragment key={score.id}>
                      <tr>
                        <td>
                          <strong>{video?.title ?? score.video_id}</strong>
                          <div className="muted">{video?.channel_title ?? "Unknown channel"}</div>
                          <div className="muted">
                            Tone: {score.tone} · 
                            <a
                              className="muted link"
                              href={score.video_url ?? `https://www.youtube.com/watch?v=${score.video_id}`}
                              target="_blank"
                              rel="noreferrer"
                            >
                              Open video
                            </a>
                          </div>
                        </td>
                        <td>{score.contextual_score.toFixed(2)}</td>
                        <td>
                          <div>Intent: {score.intent_type ?? score.intent_score.toFixed(2)}</div>
                          <div>Interest: {score.interest_topics?.join(", ") ?? score.interest_score.toFixed(2)}</div>
                          <div>Emotion: {score.emotion_type ?? score.emotion_score.toFixed(2)}</div>
                        </td>
                        <td>
                          <strong>{score.targeting_recommendation.replace("_", " ")}</strong>
                          <div>Suitability: {score.brand_suitability}</div>
                        </td>
                        <td>
                          <div className="stack">
                            <button
                              className="secondary"
                              onClick={() => setSelectedScore(isSelected ? null : score)}
                            >
                              {isSelected ? "Hide Details" : "View Details"}
                            </button>
                            <button
                              className="secondary"
                              onClick={() => scoreMutation.mutate(score.video_id)}
                            >
                              Rescore
                            </button>
                          </div>
                        </td>
                      </tr>
                      {isSelected && (
                        <tr className="inspector-row">
                          <td colSpan={5}>
                            <div className="score-inspector">
                              <div className="inspector-main">
                                <h3>{score.video_id}</h3>
                                <p>{score.reasoning ?? "No reasoning provided."}</p>

                                <div className="inspector-grid">
                                  <div className="inspector-panel polar">
                                    <h4>Signal Blend</h4>
                                    <SignalPolar
                                      intent={score.intent_score}
                                      interest={score.interest_score}
                                      emotion={score.emotion_score}
                                      similarity={score.semantic_similarity_score}
                                    />
                                  </div>
                                  <div className="inspector-panel wide">
                                    <h4>Engagement Snapshot</h4>
                                    <EngagementSnapshot video={video} averages={campaignAverages} />
                                  </div>
                                  <div className="inspector-panel stack">
                                    <h4>Suitability</h4>
                                    <SuitabilityGauge
                                      score={score.contextual_score}
                                      recommendation={score.targeting_recommendation}
                                    />
                                  </div>
                                  <div className="inspector-panel stack">
                                    <h4>Channel Trust</h4>
                                    <ChannelTrustTile video={video} />
                                  </div>
                                  <div className="inspector-panel stack">
                                    <h4>Context Highlights</h4>
                                    <HighlightsTile score={score} />
                                  </div>
                                </div>

                                <ul className="inspector-stats">
                                  <li>Semantic similarity: {score.semantic_similarity_score.toFixed(2)}</li>
                                  <li>Intent score: {score.intent_score.toFixed(2)}</li>
                                  <li>Interest score: {score.interest_score.toFixed(2)}</li>
                                  <li>Emotion score: {score.emotion_score.toFixed(2)}</li>
                                  <li>Sentiment: {score.sentiment}</li>
                                  <li>Brand safety: {score.brand_safety_status}</li>
                                </ul>

                                <button
                                  className="secondary inspector-close"
                                  onClick={() => setSelectedScore(null)}
                                >
                                  Close
                                </button>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
            {totalPages > 1 && (
              <div className="pagination">
                <button
                  className="secondary"
                  disabled={pageSafe === 0}
                  onClick={() => setCurrentPage((prev) => Math.max(prev - 1, 0))}
                >
                  Previous
                </button>
                <span>
                  Page {pageSafe + 1} of {totalPages}
                </span>
                <button
                  className="secondary"
                  disabled={pageSafe >= totalPages - 1}
                  onClick={() => setCurrentPage((prev) => Math.min(prev + 1, totalPages - 1))}
                >
                  Next
                </button>
              </div>
            )}
          </div>
        )}
      </SectionCard>

      {selectedScore && (
        <SectionCard
          title="Score Inspector"
          description="Detailed Liz AI signal readout."
        >
          {(() => {
            const video = videoLookup.get(selectedScore.video_id);
            return (
          <div className="score-inspector">
            <div className="inspector-main">
              <h3>{selectedScore.video_id}</h3>
              <p>{selectedScore.reasoning ?? "No reasoning provided."}</p>

              <div className="inspector-grid">
                <div className="inspector-panel polar">
                  <h4>Signal Blend</h4>
                  <SignalPolar
                    intent={selectedScore.intent_score}
                    interest={selectedScore.interest_score}
                    emotion={selectedScore.emotion_score}
                    similarity={selectedScore.semantic_similarity_score}
                  />
                </div>
                <div className="inspector-panel wide">
                  <h4>Engagement Snapshot</h4>
                  <EngagementSnapshot video={video} averages={campaignAverages} />
                </div>
                <div className="inspector-panel stack">
                  <h4>Suitability</h4>
                  <SuitabilityGauge
                    score={selectedScore.contextual_score}
                    recommendation={selectedScore.targeting_recommendation}
                  />
                </div>
                <div className="inspector-panel stack">
                  <h4>Channel Trust</h4>
                  <ChannelTrustTile video={video} />
                </div>
                <div className="inspector-panel stack">
                  <h4>Context Highlights</h4>
                  <HighlightsTile score={selectedScore} />
                </div>
              </div>

              <ul className="inspector-stats">
                <li>Semantic similarity: {selectedScore.semantic_similarity_score.toFixed(2)}</li>
                <li>Intent score: {selectedScore.intent_score.toFixed(2)}</li>
                <li>Interest score: {selectedScore.interest_score.toFixed(2)}</li>
                <li>Emotion score: {selectedScore.emotion_score.toFixed(2)}</li>
                <li>Sentiment: {selectedScore.sentiment}</li>
                <li>Brand safety: {selectedScore.brand_safety_status}</li>
              </ul>

              <button className="secondary" onClick={() => setSelectedScore(null)}>
                Close
              </button>
            </div>
          </div>
            );
          })()}
        </SectionCard>
      )}
    </div>
  );
};

const SuitabilityGauge = ({ score, recommendation }: { score: number; recommendation: string }) => {
  const percent = Math.max(0, Math.min(score * 100, 100));
  let tone = "gauge-neutral";
  if (recommendation === "strong_match") {
    tone = "gauge-strong";
  } else if (recommendation === "moderate_match") {
    tone = "gauge-moderate";
  } else if (recommendation === "weak_match") {
    tone = "gauge-weak";
  } else if (recommendation === "avoid") {
    tone = "gauge-avoid";
  }

  return (
    <div className="gauge">
      <div className="gauge-track">
        <div className={`gauge-fill ${tone}`} style={{ width: `${percent}%` }} />
      </div>
      <div className="gauge-meta">
        <span>{recommendation.replace("_", " ")}</span>
        <span>{percent.toFixed(0)}%</span>
      </div>
    </div>
  );
};

const SignalPolar = ({
  intent,
  interest,
  emotion,
  similarity,
}: {
  intent: number;
  interest: number;
  emotion: number;
  similarity: number;
}) => {
  const metrics = [
    { label: "Intent", value: intent, color: "#7f85ff" },
    { label: "Interest", value: interest, color: "#4db6ff" },
    { label: "Emotion", value: emotion, color: "#7ce3c0" },
    { label: "Similarity", value: similarity, color: "#f7b267" },
  ];

  const center = 110;
  const maxRadius = 90;
  const sliceAngle = (Math.PI * 2) / metrics.length;

  const polarToCartesian = (angle: number, radius: number) => {
    const x = center + radius * Math.cos(angle);
    const y = center + radius * Math.sin(angle);
    return { x, y };
  };

  const describeWedge = (start: number, end: number, radius: number) => {
    if (radius <= 0) {
      return "";
    }
    const startPoint = polarToCartesian(start, radius);
    const endPoint = polarToCartesian(end, radius);
    const largeArc = end - start > Math.PI ? 1 : 0;
    return [
      `M ${center} ${center}`,
      `L ${startPoint.x} ${startPoint.y}`,
      `A ${radius} ${radius} 0 ${largeArc} 1 ${endPoint.x} ${endPoint.y}`,
      "Z",
    ].join(" ");
  };

  return (
    <div className="polar-wrapper">
      <svg viewBox="0 0 220 220" className="polar-chart">
        {[0.25, 0.5, 0.75, 1].map((fraction) => (
          <circle
            key={fraction}
            cx={center}
            cy={center}
            r={maxRadius * fraction}
            className="polar-ring"
          />
        ))}
        {metrics.map((metric, index) => {
          const start = -Math.PI / 2 + sliceAngle * index;
          const end = start + sliceAngle;
          const path = describeWedge(start, end, Math.max(8, Math.min(metric.value, 1) * maxRadius));
          return (
            <path
              key={metric.label}
              d={path}
              className="polar-wedge"
              style={{ fill: metric.color }}
              opacity={0.85}
            />
          );
        })}
        {metrics.map((metric, index) => {
          const angle = -Math.PI / 2 + sliceAngle * index + sliceAngle / 2;
          const labelPoint = polarToCartesian(angle, maxRadius + 18);
          return (
            <text key={metric.label} x={labelPoint.x} y={labelPoint.y} className="polar-label">
              {metric.label}
            </text>
          );
        })}
      </svg>
    </div>
  );
};

const EngagementSnapshot = ({
  video,
  averages,
}: {
  video?: VideoResponseItem;
  averages: { views: number; likes: number; comments: number } | null;
}) => {
  if (!video) {
    return <p className="muted">Video metrics unavailable.</p>;
  }

  const metrics = [
    {
      label: "Views",
      value: video.view_count,
      average: averages?.views ?? 0,
    },
    {
      label: "Likes",
      value: video.like_count,
      average: averages?.likes ?? 0,
    },
    {
      label: "Comments",
      value: video.comment_count,
      average: averages?.comments ?? 0,
    },
  ];

  return (
    <div className="stat-group">
      {metrics.map(({ label, value, average }) => {
        const max = Math.max(value, average, 1);
        const actualWidth = (value / max) * 100;
        const averageWidth = (average / max) * 100;
        const delta = average ? ((value - average) / (average || 1)) * 100 : null;
        const deltaLabel = delta !== null ? `${delta >= 0 ? "+" : ""}${delta.toFixed(0)}% vs avg` : "";
        const deltaClass = delta === null ? "" : delta < 0 ? "down" : "up";

        return (
          <div key={label} className="stat-row">
            <div className="stat-header">
              <span>{label}</span>
              <strong>{formatShortNumber(value)}</strong>
            </div>
            <div className="stat-bar">
              <div className="stat-bar-avg" style={{ width: `${averageWidth}%` }} />
              <div className="stat-bar-actual" style={{ width: `${actualWidth}%` }} />
            </div>
            <div className="stat-meta">
              <span className="muted">Campaign avg {formatShortNumber(average)}</span>
              <span className={`stat-delta ${deltaClass}`}>{deltaLabel}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};

const ChannelTrustTile = ({ video }: { video?: VideoResponseItem }) => {
  if (!video) {
    return <p className="muted">Channel data unavailable.</p>;
  }

  const subscribers = video.channel_subscriber_count ?? 0;
  const channelViews = video.channel_view_count ?? 0;

  const tier = subscribers >= 1_000_000 ? "Gold" : subscribers >= 100_000 ? "Silver" : subscribers >= 10_000 ? "Bronze" : "Emerging";
  const tierClass = tier.toLowerCase();

  return (
    <div className="channel-tile">
      <div className="channel-heading">
        <div className={`channel-dot ${tierClass}`} />
        <span>{tier} tier</span>
      </div>
      <div className="channel-metrics">
        <div>
          <small>Subscribers</small>
          <strong>{formatShortNumber(subscribers)}</strong>
        </div>
        <div>
          <small>Total views</small>
          <strong>{formatShortNumber(channelViews)}</strong>
        </div>
      </div>
      {video.channel_title && <p className="muted">{video.channel_title}</p>}
    </div>
  );
};

const HighlightsTile = ({ score }: { score: VideoScore }) => {
  const chips = [
    { label: "Intent", value: score.intent_type ?? score.intent_score.toFixed(2) },
    {
      label: "Interests",
      value: score.interest_topics && score.interest_topics.length
        ? score.interest_topics.slice(0, 3).join(", ")
        : score.interest_score.toFixed(2),
    },
    { label: "Emotion", value: score.emotion_type ?? score.emotion_score.toFixed(2) },
    { label: "Tone", value: score.tone },
    { label: "Sentiment", value: score.sentiment },
  ];

  return (
    <div className="highlight-group">
      {chips.map((chip) => (
        <div key={chip.label} className="highlight-chip">
          <small>{chip.label}</small>
          <span>{chip.value}</span>
        </div>
      ))}
    </div>
  );
};

const formatShortNumber = (value: number) => {
  if (!value) return "0";
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toString();
};

export default ContentScoringPage;
