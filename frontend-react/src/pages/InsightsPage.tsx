import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import PageHeader from "../components/PageHeader";
import SectionCard from "../components/SectionCard";
import { useCampaign } from "../context/CampaignContext";
import { ScoringAPI, VideoAPI } from "../api/client";
import { VideoScore } from "../types/scoring";
import { VideoResponseItem } from "../types/video";

interface ChannelAggregate {
  channelId: string;
  channelTitle: string;
  channelUrl: string;
  avgScore: number;
  totalVideos: number;
  strongMatches: number;
  topEmotion: string;
  topTone: string;
  interestHighlights: string[];
}

interface EmotionAggregate {
  emotion: string;
  total: number;
  dominantTone: string;
}

const InsightsPage = () => {
  const { currentCampaign } = useCampaign();

  const scoresQuery = useQuery({
    queryKey: ["scores", currentCampaign?.id],
    queryFn: () => ScoringAPI.campaignScores(currentCampaign!.id),
    enabled: Boolean(currentCampaign?.id),
  });

  const videosQuery = useQuery({
    queryKey: ["videos", currentCampaign?.id],
    queryFn: () => VideoAPI.listCampaignVideos(currentCampaign!.id),
    enabled: Boolean(currentCampaign?.id),
  });

  const scores = scoresQuery.data?.data.scores ?? [];
  const videos = videosQuery.data?.data.videos ?? [];

  const videoLookup = useMemo(() => {
    const map = new Map<string, VideoResponseItem>();
    videos.forEach((video) => map.set(video.video_id, video));
    return map;
  }, [videos]);

  const channelAggregates = useMemo<ChannelAggregate[]>(() => {
    const map = new Map<string, {
      channelId: string;
      channelTitle: string;
      channelUrl: string;
      scores: VideoScore[];
      emotionCounts: Record<string, number>;
      toneCounts: Record<string, number>;
      interests: Record<string, number>;
    }>();

    scores.forEach((score) => {
      const videoMeta = videoLookup.get(score.video_id);
      const channelTitle = videoMeta?.channel_title ?? score.channel_id;
      const channelId = score.channel_id ?? videoMeta?.channel_id ?? score.channel_id;
      const channelUrl = score.channel_url || (channelId ? `https://www.youtube.com/channel/${channelId}` : "");

      if (!map.has(channelId)) {
        map.set(channelId, {
          channelId,
          channelTitle,
          channelUrl,
          scores: [],
          emotionCounts: {},
          toneCounts: {},
          interests: {},
        });
      }
      const entry = map.get(channelId)!;
      entry.scores.push(score);

      const emotion = (score.emotion_type || score.sentiment || "neutral").toLowerCase();
      entry.emotionCounts[emotion] = (entry.emotionCounts[emotion] ?? 0) + 1;

      const tone = (score.tone || "unknown").toLowerCase();
      entry.toneCounts[tone] = (entry.toneCounts[tone] ?? 0) + 1;

      const interests = score.interest_topics?.length
        ? score.interest_topics
        : score.key_topics ?? [];
      interests.forEach((topic) => {
        const key = topic.toLowerCase();
        entry.interests[key] = (entry.interests[key] ?? 0) + 1;
      });
    });

    return Array.from(map.values())
      .map((entry) => {
        const avgScore =
          entry.scores.reduce((acc, item) => acc + item.contextual_score, 0) /
          Math.max(entry.scores.length, 1);
        const strongMatches = entry.scores.filter(
          (item) => item.targeting_recommendation === "strong_match"
        ).length;

        const topEmotion = Object.entries(entry.emotionCounts)
          .sort((a, b) => b[1] - a[1])[0]?.[0] ?? "unknown";
        const topTone = Object.entries(entry.toneCounts)
          .sort((a, b) => b[1] - a[1])[0]?.[0] ?? "unknown";

        const interestHighlights = Object.entries(entry.interests)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 3)
          .map(([topic]) => topic);

        return {
          channelId: entry.channelId,
          channelTitle: entry.channelTitle,
          channelUrl: entry.channelUrl,
          avgScore,
          totalVideos: entry.scores.length,
          strongMatches,
          topEmotion,
          topTone,
          interestHighlights,
        };
      })
      .sort((a, b) => b.avgScore - a.avgScore)
      .slice(0, 8);
  }, [scores, videoLookup]);

  const emotionAggregates = useMemo<EmotionAggregate[]>(() => {
    const counts = new Map<string, { total: number; tones: Record<string, number> }>();
    scores.forEach((score) => {
      const emotion = (score.emotion_type || score.sentiment || "neutral").toLowerCase();
      if (!counts.has(emotion)) {
        counts.set(emotion, { total: 0, tones: {} });
      }
      const record = counts.get(emotion)!;
      record.total += 1;
      const tone = (score.tone || "unknown").toLowerCase();
      record.tones[tone] = (record.tones[tone] ?? 0) + 1;
    });

    return Array.from(counts.entries())
      .map(([emotion, info]) => {
        const dominantTone = Object.entries(info.tones).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "unknown";
        return { emotion, total: info.total, dominantTone };
      })
      .sort((a, b) => b.total - a.total);
  }, [scores]);

  const interestTags = useMemo(() => {
    const counts = new Map<string, number>();
    scores.forEach((score) => {
      const topics = score.interest_topics?.length
        ? score.interest_topics
        : score.key_topics ?? [];
      topics.forEach((topic) => {
        const key = topic.toLowerCase();
        counts.set(key, (counts.get(key) ?? 0) + 1);
      });
    });
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 20)
      .map(([topic, total]) => ({ topic, total }));
  }, [scores]);

  if (!currentCampaign) {
    return (
      <div className="page">
        <PageHeader title="Insights" />
        <SectionCard
          title="No campaign selected"
          description="Choose a campaign to unlock insights."
        >
          <p>Select a campaign first on the Campaign Setup page.</p>
        </SectionCard>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title="Insights"
        subtitle="Explore Liz AI signals through immersive visuals and channel intelligence."
      />

      <div className="insight-layout">
        <div className="insight-left">
          <SectionCard
            title="Emotion Constellation"
            description="Dominant emotions Liz AI detected across your scored videos. Nodes pulse with intensity; hover to see dominant tones."
          >
            {emotionAggregates.length === 0 ? (
              <p>No scored videos available to build the emotion map.</p>
            ) : (
              <div className="emotion-field">
                {emotionAggregates.map((node, index) => {
                const size = 120 + node.total * 18;
                const emotionKey = node.emotion.replace(/\s+/g, "-");
                const palette: Record<string, string> = {
                  joyful: "linear-gradient(135deg, #ffc371, #ff5f6d)",
                  neutral: "linear-gradient(135deg, #74ebd5, #acb6e5)",
                  critical: "linear-gradient(135deg, #ff6a88, #c44569)",
                  excited: "linear-gradient(135deg, #6a11cb, #2575fc)",
                  persuasive: "linear-gradient(135deg, #fbc2eb, #a6c1ee)",
                  inspired: "linear-gradient(135deg, #4facfe, #00f2fe)",
                  nostalgic: "linear-gradient(135deg, #d4fc79, #96e6a1)",
                  calm: "linear-gradient(135deg, #43cea2, #185a9d)",
                  serious: "linear-gradient(135deg, #7f7fd5, #86a8e7)",
                  unknown: "linear-gradient(135deg, #7f7fd5, #86a8e7)",
                };
                  const background =
                    palette[node.emotion as keyof typeof palette] ||
                    palette[node.dominantTone as keyof typeof palette] ||
                    palette.unknown;
                  return (
                    <div
                      key={node.emotion}
                      className={`emotion-node emotion-${emotionKey}`}
                      style={{
                      width: size,
                      height: size,
                      background,
                      animationDelay: `${index * 0.3}s`,
                    }}
                  >
                      <strong>{node.emotion}</strong>
                      <span>{node.total} videos</span>
                      <small>Tone: {node.dominantTone}</small>
                    </div>
                  );
                })}
              </div>
            )}
          </SectionCard>

          <SectionCard
            title="Interest Nebula"
            description="Clusters of interest topics that appear across your scored videos. Size reflects frequency."
          >
            {interestTags.length === 0 ? (
              <p>No interest topics detected yet.</p>
            ) : (
              <div className="interest-cloud">
                {interestTags.map((tag, index) => (
                  <span
                    key={tag.topic}
                    className="interest-tag"
                    style={{
                      fontSize: `${0.9 + tag.total * 0.15}rem`,
                      animationDelay: `${index * 0.12}s`,
                    }}
                  >
                    {tag.topic}
                  </span>
                ))}
              </div>
            )}
          </SectionCard>
        </div>

        <SectionCard
          title="Top Performing Channels"
          description="Channels ranked by average contextual score and recommendation strength."
        >
          {channelAggregates.length === 0 ? (
            <p>No channels have been scored yet.</p>
          ) : (
            <div className="channel-grid">
              {channelAggregates.map((channel) => (
                <article key={channel.channelId} className="channel-card">
                  <header>
                    <h3>{channel.channelTitle}</h3>
                    <span className="badge">Avg Score {channel.avgScore.toFixed(2)}</span>
                  </header>
                  <p>
                    <strong>{channel.strongMatches}</strong> strong matches · {channel.totalVideos} videos evaluated
                  </p>
                  <p>Emotion signature: {channel.topEmotion}</p>
                  <p>Tone signature: {channel.topTone}</p>
                  <div className="tag-row">
                    {channel.interestHighlights.map((topic) => (
                      <span key={topic} className="chip small">{topic}</span>
                    ))}
                  </div>
                  <a
                    href={channel.channelUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="secondary"
                  >
                    View Channel
                  </a>
                </article>
              ))}
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
};

export default InsightsPage;
