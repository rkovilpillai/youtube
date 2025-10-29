import { useMutation, useQuery } from "@tanstack/react-query";
import { ChangeEvent, useEffect, useMemo, useState } from "react";

import { CampaignAPI } from "../api/client";
import PageHeader from "../components/PageHeader";
import SectionCard from "../components/SectionCard";
import { useCampaign } from "../context/CampaignContext";
import { Campaign } from "../types/campaign";
import {
  audienceIntentOptions,
  audiencePersonaOptions,
  campaignGoalOptions,
  emotionOptions,
  interestClusterOptions,
  productCategoryOptions,
  toneProfileOptions,
  languageOptions,
  marketOptions,
} from "../data/campaignOptions";

type CampaignFormState = {
  name: string;
  brand_name: string;
  brand_url: string;
  product_category: string;
  campaign_goal: string;
  campaign_definition: string;
  brand_context_text: string;
  audience_intent: string[];
  audience_persona: string[];
  tone_profile: string[];
  emotion_guidance: string[];
  interest_guidance: string[];
  primary_language: string;
  primary_market: string;
};

const summarizeList = (values?: string[] | null, cap = 2) => {
  if (!values || values.length === 0) {
    return "—";
  }
  return values.slice(0, cap).join(", ");
};

const splitStoredList = (value?: string | string[] | null): string[] => {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  return value
    .split(/[,|]/)
    .map((entry) => entry.trim())
    .filter(Boolean);
};

const STORAGE_ADVANCED_KEY = "yt-campaign-advanced-open";

type MultiSelectChipsProps = {
  options: string[];
  selected: string[];
  onToggle: (value: string) => void;
};

const MultiSelectChips = ({ options, selected, onToggle }: MultiSelectChipsProps) => (
  <div className="pill-grid">
    {options.map((option) => {
      const isSelected = selected.includes(option);
      return (
        <button
          key={option}
          type="button"
          className={`pill ${isSelected ? "selected" : ""}`}
          onClick={() => onToggle(option)}
          aria-pressed={isSelected}
        >
          {option}
        </button>
      );
    })}
  </div>
);

type MultiSelectWithInputProps = MultiSelectChipsProps & {
  inputPlaceholder: string;
  onAdd: (value: string) => void;
};

const MultiSelectWithInput = ({
  options,
  selected,
  onToggle,
  inputPlaceholder,
  onAdd,
}: MultiSelectWithInputProps) => {
  const [draft, setDraft] = useState("");

  const combinedOptions = useMemo(() => {
    const set = new Set(options);
    selected.forEach((value) => {
      if (!set.has(value)) {
        set.add(value);
      }
    });
    return Array.from(set);
  }, [options, selected]);

  return (
    <div className="pill-input-group">
      <MultiSelectChips options={combinedOptions} selected={selected} onToggle={onToggle} />
      <div className="pill-input-row">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={inputPlaceholder}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              const next = draft.trim();
              if (!next) return;
              onAdd(next);
              setDraft("");
            }
          }}
        />
        <button
          type="button"
          className="pill-add"
          onClick={() => {
            const next = draft.trim();
            if (!next) return;
            onAdd(next);
            setDraft("");
          }}
        >
          Add
        </button>
      </div>
    </div>
  );
};

const CampaignSetupPage = () => {
  const initialForm = useMemo<CampaignFormState>(
    () => ({
      name: "",
      brand_name: "",
      brand_url: "",
      product_category: "",
      campaign_goal: "",
      campaign_definition: "",
      brand_context_text: "",
      audience_intent: [],
      audience_persona: [],
      tone_profile: [],
      emotion_guidance: [],
      interest_guidance: [],
      primary_language: "en",
      primary_market: "US",
    }),
    []
  );

  const [form, setForm] = useState<CampaignFormState>(() => ({ ...initialForm }));
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState<boolean>(() => {
    if (typeof window === "undefined") {
      return false;
    }
    try {
      const stored = window.localStorage.getItem(STORAGE_ADVANCED_KEY);
      return stored ? stored === "true" : false;
    } catch {
      return false;
    }
  });
  const { currentCampaign, setCurrentCampaign } = useCampaign();

  const handleFieldChange =
    (field: keyof CampaignFormState) =>
      (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        setForm((prev) => ({ ...prev, [field]: event.target.value }));
      };

  const handleSelectChange =
    (field: "product_category" | "campaign_goal" | "primary_language" | "primary_market") =>
      (event: ChangeEvent<HTMLSelectElement>) => {
        setForm((prev) => ({ ...prev, [field]: event.target.value }));
      };

  const toggleMultiValue = (field: keyof CampaignFormState, value: string) => {
    setForm((prev) => {
      const current = prev[field] as string[];
      const exists = current.includes(value);
      if (!exists && field === "emotion_guidance" && current.length >= 5) {
        return prev;
      }
      const next = exists ? current.filter((item) => item !== value) : [...current, value];
      return { ...prev, [field]: next };
    });
  };

  const addCustomValue = (field: keyof CampaignFormState, value: string) => {
    setForm((prev) => {
      const normalized = value.trim();
      if (!normalized) return prev;
      const current = prev[field] as string[];
      if (current.includes(normalized)) return prev;
      if (field === "emotion_guidance" && current.length >= 5) return prev;
      return { ...prev, [field]: [...current, normalized] };
    });
  };

  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem(STORAGE_ADVANCED_KEY, String(advancedOpen));
      } catch {
        // Ignore storage failures
      }
    }
  }, [advancedOpen]);

  const campaignsQuery = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => CampaignAPI.list(),
  });

  const campaigns = campaignsQuery.data?.data.campaigns ?? [];

  const buildPayload = (values: CampaignFormState) => {
    const trimmedBrandUrl = values.brand_url.trim();
    const trimmedBrandContext = values.brand_context_text.trim();
    const joinOrNull = (entries: string[]) => (entries.length ? entries.join(", ") : null);

    return {
      name: values.name,
      brand_name: values.brand_name,
      brand_url: trimmedBrandUrl || null,
      product_category: values.product_category,
      campaign_goal: values.campaign_goal,
      campaign_definition: values.campaign_definition,
      brand_context_text: trimmedBrandContext || null,
      audience_intent: joinOrNull(values.audience_intent),
      audience_persona: joinOrNull(values.audience_persona),
      tone_profile: joinOrNull(values.tone_profile),
      emotion_guidance: values.emotion_guidance.length ? values.emotion_guidance : null,
      interest_guidance: values.interest_guidance.length ? values.interest_guidance : null,
      primary_language: values.primary_language || "en",
      primary_market: values.primary_market || "US",
    };
  };

  const createMutation = useMutation({
    mutationFn: () => CampaignAPI.create(buildPayload(form)),
    onSuccess: (payload) => {
      const newCampaign = payload.data;
      setForm(() => ({ ...initialForm }));
      setCurrentCampaign(newCampaign as Campaign);
      campaignsQuery.refetch();
      setSubmitError(null);
    },
    onError: (error: unknown) => {
      if (error instanceof Error) {
        setSubmitError(error.message);
      } else {
        setSubmitError("Failed to create campaign. Please try again.");
      }
    },
  });

  const handleSelect = (campaign: Campaign) => {
    setCurrentCampaign(campaign);
  };

  const neuroSnapshot = useMemo(() => {
    if (!currentCampaign) return null;

    const intents = splitStoredList(currentCampaign.audience_intent);
    const personas = splitStoredList(currentCampaign.audience_persona);
    const tones = splitStoredList(currentCampaign.tone_profile);
    const emotions = currentCampaign.emotion_guidance ?? [];
    const interests = currentCampaign.interest_guidance ?? [];
    const localeParts = [
      currentCampaign.primary_language?.toUpperCase(),
      currentCampaign.primary_market?.toUpperCase(),
    ].filter(Boolean);

    const sentences: string[] = [];

    if (personas.length) {
      sentences.push(`Designed for ${personas.join(", ")}`);
    }

    if (intents.length) {
      sentences.push(`Guides a ${intents.join(", ")} journey`);
    }

    if (tones.length) {
      sentences.push(`Tone anchored in ${tones.join(", ")}`);
    }

    if (emotions.length) {
      sentences.push(`Emotion cues: ${emotions.join(", ")}`);
    }

    if (interests.length) {
      sentences.push(`Interest clusters: ${interests.join(", ")}`);
    }

    if (localeParts.length) {
      sentences.push(`Localized for ${localeParts.join("-")}`);
    }

    return sentences.length ? sentences.join(". ") : null;
  }, [currentCampaign]);

  const renderGuidance = (values?: string[] | null) => {
    if (!values || values.length === 0) {
      return <p className="muted">—</p>;
    }

    return (
      <div className="chip-row">
        {values.map((value) => (
          <span key={value} className="chip small">
            {value}
          </span>
        ))}
      </div>
    );
  };

  return (
    <div className="page">
      <PageHeader
        title="Campaign Setup"
        subtitle="Create and manage contextual video campaigns"
      />

      <div className="grid-two">
        <SectionCard
          title="New Campaign"
          description="Fill out the campaign brief to generate rich contextual data."
        >
          <form
            className="campaign-form"
            onSubmit={(e) => {
              e.preventDefault();
              createMutation.mutate();
            }}
          >
            <div className="form-panel">
              <div className="form-panel-header">
                <h4>Campaign Fundamentals</h4>
                <span>Core information powering every downstream workflow.</span>
              </div>
              <div className="form-panel-grid">
                <label>
                  <span>Campaign Name</span>
                  <input
                    value={form.name}
                    onChange={handleFieldChange("name")}
                    required
                    placeholder="Summer Tech Launch"
                  />
                </label>
                <label>
                  <span>Brand Name</span>
                  <input
                    value={form.brand_name}
                    onChange={handleFieldChange("brand_name")}
                    required
                    placeholder="TechCo"
                  />
                </label>
                <label>
                  <span>Brand URL</span>
                  <input
                    value={form.brand_url}
                    onChange={handleFieldChange("brand_url")}
                    placeholder="https://www.techco.com"
                  />
                </label>
                <label>
                  <span>Product Category</span>
                  <select
                    value={form.product_category}
                    onChange={handleSelectChange("product_category")}
                    required
                  >
                    <option value="">Select a category</option>
                    {productCategoryOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Campaign Goal</span>
                  <select
                    value={form.campaign_goal}
                    onChange={handleSelectChange("campaign_goal")}
                    required
                  >
                    <option value="">Select a goal</option>
                    {campaignGoalOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Primary Language</span>
                  <select
                    value={form.primary_language}
                    onChange={handleSelectChange("primary_language")}
                    required
                  >
                    {languageOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Primary Market</span>
                  <select
                    value={form.primary_market}
                    onChange={handleSelectChange("primary_market")}
                    required
                  >
                    {marketOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="full-width">
                  <span>Campaign Definition</span>
                  <textarea
                    value={form.campaign_definition}
                    onChange={handleFieldChange("campaign_definition")}
                    rows={4}
                    required
                    placeholder="Summarise the launch narrative, hero product, and success measures."
                  />
                </label>
                <label className="full-width">
                  <span>Brand Context (optional)</span>
                  <textarea
                    value={form.brand_context_text}
                    onChange={handleFieldChange("brand_context_text")}
                    rows={3}
                    placeholder="Tone of voice, hero messages, creative guardrails."
                  />
                </label>
              </div>
            </div>

            <div className={`advanced-card ${advancedOpen ? "open" : ""}`}>
              <div className="advanced-header">
                <div>
                  <h4>Advanced Contextual Controls</h4>
                  <span>Optional neuro-contextual guidance for deeper personalisation.</span>
                </div>
                <button
                  type="button"
                  className="secondary toggle-advanced"
                  onClick={() => setAdvancedOpen((prev) => !prev)}
                >
                  {advancedOpen ? "Hide" : "Show"}
                </button>
              </div>
              {advancedOpen && (
                <div className="advanced-content">
                  <div className="form-subpanel">
                    <div className="form-subpanel-header">
                      <h5>Audience & Intent</h5>
                      <p>Define who you want to resonate with and how you want to guide them.</p>
                    </div>
                    <label>
                      <span>Audience Intent</span>
                      <MultiSelectWithInput
                        options={audienceIntentOptions}
                        selected={form.audience_intent}
                        onToggle={(value) => toggleMultiValue("audience_intent", value)}
                        onAdd={(value) => addCustomValue("audience_intent", value)}
                        inputPlaceholder="Add a custom intent and press Enter"
                      />
                      <p className="helper-text">Select or add multiple intents to reflect mixed journeys.</p>
                    </label>
                    <label>
                      <span>Audience Personas</span>
                      <MultiSelectWithInput
                        options={audiencePersonaOptions}
                        selected={form.audience_persona}
                        onToggle={(value) => toggleMultiValue("audience_persona", value)}
                        onAdd={(value) => addCustomValue("audience_persona", value)}
                        inputPlaceholder="Add a custom persona and press Enter"
                      />
                    </label>
                    <label>
                      <span>Tone Profile</span>
                      <MultiSelectWithInput
                        options={toneProfileOptions}
                        selected={form.tone_profile}
                        onToggle={(value) => toggleMultiValue("tone_profile", value)}
                        onAdd={(value) => addCustomValue("tone_profile", value)}
                        inputPlaceholder="Add a custom tone and press Enter"
                      />
                    </label>
                    <label>
                      <span>Interest Guidance</span>
                      <MultiSelectWithInput
                        options={interestClusterOptions}
                        selected={form.interest_guidance}
                        onToggle={(value) => toggleMultiValue("interest_guidance", value)}
                        onAdd={(value) => addCustomValue("interest_guidance", value)}
                        inputPlaceholder="Add a custom interest cluster and press Enter"
                      />
                    </label>
                  </div>

                  <div className="form-subpanel">
                    <div className="form-subpanel-header">
                      <h5>Emotional Palette</h5>
                      <p>Signal the emotional cues that best prime your audience.</p>
                    </div>
                    <label>
                      <span>Emotion Guidance</span>
                      <MultiSelectWithInput
                        options={emotionOptions}
                        selected={form.emotion_guidance}
                        onToggle={(value) => toggleMultiValue("emotion_guidance", value)}
                        onAdd={(value) => addCustomValue("emotion_guidance", value)}
                        inputPlaceholder="Add a custom emotion and press Enter"
                      />
                      <p className="helper-text">Pick up to five emotions to keep the signal focused.</p>
                    </label>
                  </div>
                </div>
              )}
            </div>

            {submitError && <p className="error-text">{submitError}</p>}

            <div className="button-row">
              <button className="primary" type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creating…" : "Create Campaign"}
              </button>
            </div>
          </form>
        </SectionCard>

        <SectionCard
          title="Recent Campaigns"
          description="Quick access to your latest work."
        >
          {campaignsQuery.isLoading && <div>Loading…</div>}
          {!campaignsQuery.isLoading && campaigns.length === 0 && (
            <p>No campaigns yet. Create one to get started.</p>
          )}
          {campaigns.length > 0 && (
            <ul className="list">
              {campaigns.map((campaign) => {
                const active = currentCampaign?.id === campaign.id;
                const intentList = splitStoredList(campaign.audience_intent);
                const toneList = splitStoredList(campaign.tone_profile);
                const emotionList = campaign.emotion_guidance ?? [];
                const interestList = campaign.interest_guidance ?? [];
                const showAdvancedBadge =
                  intentList.length || toneList.length || emotionList.length || interestList.length;
                return (
                  <li key={campaign.id} className={active ? "active-item" : ""}>
                    <div className="list-item-body">
                      <h4>{campaign.name}</h4>
                      <p>
                        {campaign.brand_name} · {campaign.product_category}
                      </p>
                      <p className="meta-line">
                        Intent: {intentList.length ? intentList.join(", ") : "—"} · Tone:{" "}
                        {toneList.length ? toneList.join(", ") : "—"}
                      </p>
                      <p className="meta-line">
                        Emotions: {summarizeList(emotionList)} · Interests: {summarizeList(interestList)}
                      </p>
                      <p className="meta-line">
                        Locale:{" "}
                        {[
                          campaign.primary_language?.toUpperCase() ?? "EN",
                          campaign.primary_market?.toUpperCase() ?? "US",
                        ].join("-")}
                      </p>
                      {showAdvancedBadge && <span className="advanced-indicator">Advanced guidance active</span>}
                    </div>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => handleSelect(campaign)}
                    >
                      {active ? "Selected" : "Set Active"}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </SectionCard>
      </div>

      <SectionCard
        title="Active Campaign"
        description="This campaign will be used across keywords, video fetch, and scoring."
      >
        {currentCampaign ? (
          (() => {
            const intentList = splitStoredList(currentCampaign.audience_intent);
            const personaList = splitStoredList(currentCampaign.audience_persona);
            const toneList = splitStoredList(currentCampaign.tone_profile);
            const emotions = currentCampaign.emotion_guidance ?? [];
            const interests = currentCampaign.interest_guidance ?? [];
            return (
              <div className="active-details">
                <h3>{currentCampaign.name}</h3>
                <p>
                  <strong>Brand:</strong> {currentCampaign.brand_name}
                </p>
                <p>
                  <strong>Category:</strong> {currentCampaign.product_category}
                </p>
                <p>
                  <strong>Goal:</strong> {currentCampaign.campaign_goal}
                </p>
                <p>
                  <strong>Locale:</strong>{" "}
                  {[
                    currentCampaign.primary_language?.toUpperCase() ?? "EN",
                    currentCampaign.primary_market?.toUpperCase() ?? "US",
                  ].join("-")}
                </p>
                <p>
                  <strong>Created:</strong> {new Date(currentCampaign.created_at).toLocaleString()}
                </p>
                <div className="active-grid">
                  <div>
                    <h5>Audience Intent</h5>
                    <p>{intentList.length ? intentList.join(", ") : "—"}</p>
                  </div>
                  <div>
                    <h5>Audience Personas</h5>
                    <p>{personaList.length ? personaList.join(", ") : "—"}</p>
                  </div>
                  <div>
                    <h5>Tone Profile</h5>
                    <p>{toneList.length ? toneList.join(", ") : "—"}</p>
                  </div>
                </div>
                <div className="active-grid">
                  <div>
                    <h5>Emotion Palette</h5>
                    {renderGuidance(emotions)}
                  </div>
                  <div>
                    <h5>Interest Guidance</h5>
                    {renderGuidance(interests)}
                  </div>
                </div>
                {neuroSnapshot && (
                  <div className="neuro-narrative">
                    <h5>Neuro Narrative</h5>
                    <p>{neuroSnapshot}</p>
                  </div>
                )}
              </div>
            );
          })()
        ) : (
          <p>Select a campaign from the list to activate it.</p>
        )}
      </SectionCard>
    </div>
  );
};

export default CampaignSetupPage;
