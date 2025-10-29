import { NavLink } from "react-router-dom";
import { ReactNode } from "react";

import { useCampaign } from "../context/CampaignContext";

import "./AppShell.css";

const navItems = [
  { label: "Campaign Setup", path: "/" },
  { label: "Keyword Generation", path: "/keywords" },
  { label: "Video Fetch", path: "/videos" },
  { label: "Content Scoring", path: "/scoring" },
  { label: "Insights", path: "/insights" },
];

interface AppShellProps {
  children: ReactNode;
}

const AppShell = ({ children }: AppShellProps) => {
  const { currentCampaign } = useCampaign();
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1 className="logo">YT Contextual</h1>
        {currentCampaign ? (
          <div className="active-campaign">
            <span className="badge">Active Campaign</span>
            <strong>{currentCampaign.name}</strong>
            <small>{currentCampaign.brand_name}</small>
          </div>
        ) : (
          <div className="active-campaign">
            <span className="badge muted">No campaign selected</span>
          </div>
        )}
        <nav>
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `nav-item ${isActive ? "active" : ""}`
              }
              end
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
};

export default AppShell;
