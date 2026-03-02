import { NavLink, Route, Routes } from "react-router-dom";
import { Overview } from "./pages/Overview";
import { Leads } from "./pages/Leads";
import { Campaigns } from "./pages/Campaigns";
import { Sources } from "./pages/Sources";
import { RunCycle } from "./pages/RunCycle";
import "./App.css";

const navItems = [
  { to: "/", label: "Overview", icon: IconOverview },
  { to: "/leads", label: "Leads", icon: IconLeads },
  { to: "/campaigns", label: "Campaigns", icon: IconCampaigns },
  { to: "/sources", label: "Sources", icon: IconSources },
  { to: "/run-cycle", label: "Run cycle", icon: IconRun },
];

function IconOverview() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
    </svg>
  );
}

function IconLeads() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}

function IconCampaigns() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      <line x1="8" y1="6" x2="18" y2="6" />
      <line x1="8" y1="10" x2="18" y2="10" />
    </svg>
  );
}

function IconSources() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
      <line x1="12" y1="22.08" x2="12" y2="12" />
    </svg>
  );
}

function IconRun() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  );
}

function App() {
  return (
    <div className="app">
      <aside className="sidebar" aria-label="Navigation">
        <div className="sidebar-brand">
          <span className="sidebar-brand-icon">⚡</span>
          <span className="sidebar-brand-text">Speed to Response</span>
        </div>
        <nav className="sidebar-nav">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) => `sidebar-link ${isActive ? "active" : ""}`}
            >
              <Icon />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="sidebar-footer-label">Eolas Medical</span>
        </div>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/leads" element={<Leads />} />
          <Route path="/campaigns" element={<Campaigns />} />
          <Route path="/sources" element={<Sources />} />
          <Route path="/run-cycle" element={<RunCycle />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
