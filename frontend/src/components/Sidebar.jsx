import { Fragment } from "react";
import {
  LayoutDashboard,
  ArrowUpRight,
  ArrowDownLeft,
  Receipt,
  AlertTriangle,
  FileText,
  UploadCloud,
  BarChart3,
  Settings,
  Building2,
  LogOut,
  ShieldCheck,
  History,
} from "lucide-react";

export function Sidebar({ currentTab, setCurrentTab, anomalyCount = 0, user, activeBusiness, onLogout }) {
  const navItems = [
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, section: "Core Overview" },
    { id: "sales", label: "Sales ↔ GSTR-1", icon: ArrowUpRight, section: "Reconciliation" },
    { id: "purchase", label: "Purchase ↔ GSTR-2A", icon: ArrowDownLeft, section: "Reconciliation" },
    { id: "gstr3b", label: "GSTR-3B Summary", icon: Receipt, section: "Tax Return" },
    { id: "anomalies", label: "Anomaly Center", icon: AlertTriangle, section: "Audit & Risk", badge: anomalyCount },
    { id: "invoices", label: "Invoice Records", icon: FileText, section: "Data Management" },
    { id: "upload", label: "CSV Ingestion", icon: UploadCloud, section: "Data Management" },
    { id: "history", label: "Import History", icon: History, section: "Data Management" },
    { id: "reports", label: "Reports & Export", icon: BarChart3, section: "Statutory Reporting" },
    { id: "settings", label: "Configuration", icon: Settings, section: "Settings" },
  ];

  let lastSection = "";

  return (
    <aside className="sidebar">
      {/* Original Modern Brand Header */}
      <div className="sidebar-header">
        <div className="sidebar-brand-mark">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="2" y="3" width="20" height="18" rx="4" fill="url(#saffronGrad)" />
            <path d="M7 8h10M7 12h5M7 16h8" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" />
            <circle cx="16" cy="14" r="3.5" fill="#1c1411" stroke="#ffffff" strokeWidth="1.5" />
            <path d="M15 14l1 1 2-2" stroke="#ffffff" strokeWidth="1.2" strokeLinecap="round" />
            <defs>
              <linearGradient id="saffronGrad" x1="2" y1="3" x2="22" y2="21" gradientUnits="userSpaceOnUse">
                <stop stopColor="#ea580c" />
                <stop offset="1" stopColor="#c2410c" />
              </linearGradient>
            </defs>
          </svg>
        </div>
        <div className="sidebar-logo-text">
          <h2>GST Platform</h2>
          <span>MSME Compliance Suite</span>
        </div>
      </div>

      {/* Navigation Sections */}
      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const showSection = item.section !== lastSection;
          lastSection = item.section;

          return (
            <Fragment key={item.id}>
              {showSection && <div className="nav-section-title">{item.section}</div>}
              <button
                type="button"
                className={`nav-item ${currentTab === item.id ? "active" : ""}`}
                onClick={() => setCurrentTab(item.id)}
              >
                <item.icon size={17} className="nav-item-icon" />
                <span className="nav-item-text">{item.label}</span>
                {item.badge !== undefined && item.badge > 0 && (
                  <span className="nav-badge">{item.badge}</span>
                )}
              </button>
            </Fragment>
          );
        })}
      </nav>

      {/* Bottom Profile / Business Card */}
      <div className="sidebar-footer">
        <div className="sidebar-business-card">
          <div className="biz-avatar">
            <Building2 size={16} />
          </div>
          <div className="biz-details">
            <div className="biz-name">{activeBusiness ? activeBusiness.name : "Select Business"}</div>
            <div className="biz-gstin">{activeBusiness ? activeBusiness.gstin : "No GSTIN"}</div>
          </div>
        </div>

        {user && (
          <div className="sidebar-user-strip">
            <div className="user-details">
              <div className="user-name">
                <ShieldCheck size={12} color="#ea580c" style={{ display: "inline", marginRight: 4 }} />
                {user.name}
              </div>
              <div className="user-email">{user.email}</div>
            </div>
            {onLogout && (
              <button
                type="button"
                className="user-logout-btn"
                title="Sign Out"
                onClick={onLogout}
              >
                <LogOut size={14} />
              </button>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
