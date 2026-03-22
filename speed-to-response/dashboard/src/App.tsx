import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { Leads } from "./pages/Leads";
import { Campaigns } from "./pages/Campaigns";
import "./App.css";

const navItems = [
  { to: "/leads", label: "Emails", icon: IconLeads },
  { to: "/campaigns", label: "LinkedIn", icon: IconCampaigns },
];

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
              end
              className={({ isActive }) => `sidebar-link ${isActive ? "active" : ""}`}
            >
              <Icon />
              <span className="sidebar-link-label">{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="sidebar-footer-label">Eolas Medical</span>
        </div>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/" element={<Navigate to="/leads" replace />} />
          <Route path="/leads" element={<Leads />} />
          <Route path="/campaigns" element={<Campaigns />} />
          <Route path="*" element={<Navigate to="/leads" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
