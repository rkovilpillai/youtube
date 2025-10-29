import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  ReactNode,
} from "react";

import { Campaign } from "../types/campaign";

interface CampaignContextValue {
  currentCampaign: Campaign | null;
  setCurrentCampaign: (campaign: Campaign | null) => void;
}

const CampaignContext = createContext<CampaignContextValue | null>(null);

const STORAGE_KEY = "yt-current-campaign";

export const CampaignProvider = ({ children }: { children: ReactNode }) => {
  const [currentCampaign, setCurrentCampaignState] = useState<Campaign | null>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      return JSON.parse(raw) as Campaign;
    } catch (error) {
      console.warn("Failed to parse stored campaign", error);
      return null;
    }
  });

  useEffect(() => {
    if (currentCampaign) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(currentCampaign));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [currentCampaign]);

  const value = useMemo(
    () => ({
      currentCampaign,
      setCurrentCampaign: (campaign: Campaign | null) => setCurrentCampaignState(campaign),
    }),
    [currentCampaign]
  );

  return <CampaignContext.Provider value={value}>{children}</CampaignContext.Provider>;
};

export const useCampaign = () => {
  const context = useContext(CampaignContext);
  if (!context) {
    throw new Error("useCampaign must be used within a CampaignProvider");
  }
  return context;
};
