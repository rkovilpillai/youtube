import { Outlet, Route, Routes } from "react-router-dom";
import { Suspense } from "react";

import AppShell from "./components/AppShell";
import CampaignSetupPage from "./pages/CampaignSetupPage";
import KeywordGenerationPage from "./pages/KeywordGenerationPage";
import VideoFetchPage from "./pages/VideoFetchPage";
import ContentScoringPage from "./pages/ContentScoringPage";
import InsightsPage from "./pages/InsightsPage";

const App = () => {
  return (
    <Routes>
      <Route
        element={
          <AppShell>
            <Suspense fallback={<div className="page-loading">Loading…</div>}>
              <Outlet />
            </Suspense>
          </AppShell>
        }
      >
        <Route path="/" element={<CampaignSetupPage />} />
        <Route path="/keywords" element={<KeywordGenerationPage />} />
        <Route path="/videos" element={<VideoFetchPage />} />
        <Route path="/scoring" element={<ContentScoringPage />} />
        <Route path="/insights" element={<InsightsPage />} />
      </Route>
    </Routes>
  );
};

export default App;
