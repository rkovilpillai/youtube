import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import App from "./App";
import "./index.css";
import { CampaignProvider } from "./context/CampaignContext";

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <CampaignProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </CampaignProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
