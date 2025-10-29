import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { KeywordAPI } from "../api/client";
import PageHeader from "../components/PageHeader";
import SectionCard from "../components/SectionCard";
import { useCampaign } from "../context/CampaignContext";
import { Keyword, KeywordType } from "../types/keyword";

const keywordTypeLabels: Record<KeywordType, string> = {
  "core": "Core Keywords",
  "long-tail": "Long-tail Keywords",
  "related": "Related Topics",
  "intent-based": "Intent-based Keywords",
};

const MAX_KEYWORDS_PER_TYPE = 30;

const KeywordGenerationPage = () => {
  const { currentCampaign } = useCampaign();
  const [generationConfig, setGenerationConfig] = useState({
    num_core_keywords: 10,
    num_long_tail: 15,
    num_related: 10,
    num_intent_based: 10,
  });

  const manualFormInitial = useMemo(
    () => ({ keyword: "", keyword_type: "core" as KeywordType, relevance_score: 0.8 }),
    []
  );
  const [manualForm, setManualForm] = useState(manualFormInitial);
  const [manualMessage, setManualMessage] = useState<string | null>(null);

  const keywordsQuery = useQuery({
    queryKey: ["keywords", currentCampaign?.id],
    queryFn: () => KeywordAPI.list(currentCampaign!.id),
    enabled: Boolean(currentCampaign?.id),
  });

  const groupedKeywords = useMemo(() => {
    const map: Record<KeywordType, Keyword[]> = {
      "core": [],
      "long-tail": [],
      "related": [],
      "intent-based": [],
    };
    const keywords = keywordsQuery.data?.data.keywords ?? [];
    keywords.forEach((kw) => {
      map[kw.keyword_type].push(kw);
    });
    return map;
  }, [keywordsQuery.data]);

  const generateMutation = useMutation({
    mutationFn: () =>
      KeywordAPI.generate({
        campaign_id: currentCampaign!.id,
        ...generationConfig,
      }),
    onSuccess: () => keywordsQuery.refetch(),
  });

  type ManualPayload = {
    tokens: string[];
    keyword_type: KeywordType;
    relevance_score: number;
  };

  const manualMutation = useMutation({
    mutationFn: async ({ tokens, keyword_type, relevance_score }: ManualPayload) => {
      setManualMessage(null);

      const existingCount = groupedKeywords[keyword_type].length;
      const remainingSlots = MAX_KEYWORDS_PER_TYPE - existingCount;

      if (remainingSlots <= 0) {
        throw new Error("This keyword bucket already has 30 entries. Remove some before adding more.");
      }

      const trimmedTokens = tokens
        .map((token) => token.trim())
        .filter(Boolean);

      if (!trimmedTokens.length) {
        throw new Error("Enter at least one keyword.");
      }

      const keywordsToAdd = trimmedTokens.slice(0, remainingSlots);

      for (const keyword of keywordsToAdd) {
        await KeywordAPI.addManualKeyword({
          campaign_id: currentCampaign!.id,
          keyword,
          keyword_type,
          relevance_score,
        });
      }

      return {
        added: keywordsToAdd.length,
        skipped: trimmedTokens.length - keywordsToAdd.length,
      };
    },
    onSuccess: ({ added, skipped }) => {
      setManualForm(manualFormInitial);
      if (skipped > 0) {
        setManualMessage(
          `Added ${added} keyword${added === 1 ? "" : "s"}. Remove ${skipped} more before adding the rest (limit ${MAX_KEYWORDS_PER_TYPE}).`
        );
      } else {
        setManualMessage(null);
      }
      keywordsQuery.refetch();
    },
    onError: (error: unknown) => {
      if (error instanceof Error) {
        setManualMessage(error.message);
      } else {
        setManualMessage("Failed to add keywords. Please try again.");
      }
    },
  });

  const handleExport = (type?: KeywordType) => {
    const allKeywords = keywordsQuery.data?.data.keywords ?? [];
    const filtered = type ? allKeywords.filter((kw) => kw.keyword_type === type) : allKeywords;
    if (filtered.length === 0) return;

    const csv = ["keyword,keyword_type,relevance_score,source"].concat(
      filtered.map((kw) =>
        [kw.keyword, kw.keyword_type, kw.relevance_score.toFixed(2), kw.source].join(",")
      )
    );
    const blob = new Blob([csv.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    const safeName = (currentCampaign?.name ?? "campaign").replace(/[^a-z0-9_-]+/gi, "-");
    link.setAttribute("download", `${safeName}_keywords${type ? `_${type}` : ""}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  if (!currentCampaign) {
    return (
      <div className="page">
        <PageHeader title="Keyword Generation" />
        <SectionCard
          title="No campaign selected"
          description="Choose a campaign from the Campaign Setup page to generate keywords."
        >
          <p>Select a campaign to unlock keyword generation features.</p>
        </SectionCard>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title="Keyword Generation"
        subtitle={`Generate contextual keywords for ${currentCampaign.name}.`}
        actions={
          <button className="secondary" onClick={() => handleExport()} disabled={keywordsQuery.isLoading}>
            Export All CSV
          </button>
        }
      />

      <div className="grid-two">
        <SectionCard
          title="Generation Settings"
          description="Customize how Liz AI generates keywords across different categories."
        >
          <form
            className="form-grid"
            onSubmit={(e) => {
              e.preventDefault();
              generateMutation.mutate();
            }}
          >
            <label>
              <span>Core Keywords</span>
              <input
                type="number"
                min={5}
                max={20}
                value={generationConfig.num_core_keywords}
                onChange={(e) =>
                  setGenerationConfig({ ...generationConfig, num_core_keywords: Number(e.target.value) })
                }
              />
            </label>
            <label>
              <span>Long-tail Keywords</span>
              <input
                type="number"
                min={10}
                max={30}
                value={generationConfig.num_long_tail}
                onChange={(e) =>
                  setGenerationConfig({ ...generationConfig, num_long_tail: Number(e.target.value) })
                }
              />
            </label>
            <label>
              <span>Related Topics</span>
              <input
                type="number"
                min={5}
                max={20}
                value={generationConfig.num_related}
                onChange={(e) =>
                  setGenerationConfig({ ...generationConfig, num_related: Number(e.target.value) })
                }
              />
            </label>
            <label>
              <span>Intent-based Keywords</span>
              <input
                type="number"
                min={5}
                max={20}
                value={generationConfig.num_intent_based}
                onChange={(e) =>
                  setGenerationConfig({ ...generationConfig, num_intent_based: Number(e.target.value) })
                }
              />
            </label>
            <button className="primary" type="submit" disabled={generateMutation.isPending}>
              {generateMutation.isPending ? "Generating…" : "Generate Keywords"}
            </button>
          </form>
        </SectionCard>

        <SectionCard
          title="Manual Keyword"
          description="Add bespoke terms to complement AI-generated results."
        >
          <form
            className="form-grid"
            onSubmit={(e) => {
              e.preventDefault();
              const tokens = manualForm.keyword.split(/[\n,]/);
              if (tokens.filter((token) => token.trim()).length === 0) {
                setManualMessage("Enter at least one keyword separated by commas.");
                return;
              }
              manualMutation.mutate({
                tokens,
                keyword_type: manualForm.keyword_type,
                relevance_score: manualForm.relevance_score,
              });
            }}
          >
            <label>
              <span>Keyword</span>
              <input
                value={manualForm.keyword}
                onChange={(e) => {
                  setManualMessage(null);
                  setManualForm({ ...manualForm, keyword: e.target.value });
                }}
                required
                placeholder="Comma-separated keywords (max 30 per bucket)"
              />
            </label>
            <label>
              <span>Keyword Type</span>
              <select
                value={manualForm.keyword_type}
                onChange={(e) => {
                  setManualMessage(null);
                  setManualForm({ ...manualForm, keyword_type: e.target.value as KeywordType });
                }}
              >
                <option value="core">Core</option>
                <option value="long-tail">Long Tail</option>
                <option value="related">Related</option>
                <option value="intent-based">Intent-Based</option>
              </select>
            </label>
            <label>
              <span>Relevance Score</span>
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={manualForm.relevance_score}
                onChange={(e) => setManualForm({ ...manualForm, relevance_score: Number(e.target.value) })}
              />
            </label>
            <button
              className="secondary"
              type="submit"
              disabled={
                manualMutation.isPending ||
                groupedKeywords[manualForm.keyword_type].length >= MAX_KEYWORDS_PER_TYPE
              }
            >
              {manualMutation.isPending ? "Adding…" : "Add Keyword"}
            </button>
            <p className="helper-text">
              Remaining slots in {manualForm.keyword_type.replace("-", " ")}:{" "}
              {Math.max(
                0,
                MAX_KEYWORDS_PER_TYPE - groupedKeywords[manualForm.keyword_type].length
              )}{" "}
              / {MAX_KEYWORDS_PER_TYPE}
            </p>
            {manualMessage && <p className="error-text">{manualMessage}</p>}
          </form>
        </SectionCard>
      </div>

      {keywordsQuery.isLoading ? (
        <SectionCard title="Keywords" description="Fetching latest keywords.">
          <div>Loading keyword inventory…</div>
        </SectionCard>
      ) : (
        <div className="keyword-grid">
          {(Object.keys(groupedKeywords) as KeywordType[]).map((type) => {
            const keywords = groupedKeywords[type];
            const limitReached = keywords.length >= MAX_KEYWORDS_PER_TYPE;
            return (
              <SectionCard
                key={type}
                title={`${keywordTypeLabels[type]} (${keywords.length}/${MAX_KEYWORDS_PER_TYPE})`}
                description={`Keywords targeting ${type.replace("-", " ")}`}
              >
                <div className="keyword-actions">
                  <button className="secondary" onClick={() => handleExport(type)} disabled={keywords.length === 0}>
                    Export CSV
                  </button>
                </div>
                {keywords.length === 0 ? (
                  <p>No keywords in this bucket yet.</p>
                ) : (
                  <div className="keyword-table-wrapper">
                    <table className="keyword-table">
                      <thead>
                        <tr>
                          <th>Keyword</th>
                          <th>Relevance</th>
                          <th>Source</th>
                          <th>Added</th>
                        </tr>
                      </thead>
                      <tbody>
                        {keywords.map((kw) => (
                          <tr key={kw.id}>
                            <td>{kw.keyword}</td>
                            <td>{kw.relevance_score.toFixed(2)}</td>
                            <td>{kw.source === "ai-generated" ? "LIZ" : "Manual"}</td>
                            <td>{new Date(kw.created_at).toLocaleDateString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {limitReached && <p className="helper-text">Limit reached. Remove keywords to free up slots.</p>}
              </SectionCard>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default KeywordGenerationPage;
