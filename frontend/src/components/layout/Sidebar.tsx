import React from "react";
import {
  BookOpen,
  LayoutDashboard,
  CheckCircle2,
  Compass,
  Bot,
  Cpu,
  Layers,
  Sparkles,
  Home,
} from "lucide-react";
import { Badge } from "../ui/Badge";

export interface NavItem {
  id: string;
  label: string;
  path: string;
  icon: React.ReactNode;
  badge?: string;
  badgeVariant?: "neutral" | "info" | "success" | "warning";
}

interface SidebarProps {
  currentPath: string;
  onNavigate: (path: string) => void;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentPath,
  onNavigate,
  onCloseMobile,
}) => {
  const navItems: NavItem[] = [
    {
      id: "landing",
      label: "Home",
      path: "/",
      icon: <Home size={18} strokeWidth={2} />,
    },
    {
      id: "dashboard",
      label: "Dashboard",
      path: "/dashboard",
      icon: <LayoutDashboard size={18} strokeWidth={2} />,
    },
    {
      id: "library",
      label: "Paper Library",
      path: "/library",
      icon: <BookOpen size={18} strokeWidth={2} />,
    },
    {
      id: "quality",
      label: "Quality Center",
      path: "/quality",
      icon: <CheckCircle2 size={18} strokeWidth={2} />,
      badge: "Phase 2",
      badgeVariant: "neutral",
    },
    {
      id: "explorer",
      label: "Research Explorer",
      path: "/explorer",
      icon: <Compass size={18} strokeWidth={2} />,
      badge: "Phase 5",
      badgeVariant: "neutral",
    },
    {
      id: "assistant",
      label: "Assistant",
      path: "/assistant",
      icon: <Bot size={18} strokeWidth={2} />,
      badge: "Phase 4",
      badgeVariant: "neutral",
    },
    {
      id: "model-lab",
      label: "Model Lab",
      path: "/model-lab",
      icon: <Cpu size={18} strokeWidth={2} />,
      badge: "Phase 3",
      badgeVariant: "neutral",
    },
  ];

  const handleItemClick = (path: string) => {
    onNavigate(path);
    if (onCloseMobile) {
      onCloseMobile();
    }
  };

  return (
    <aside
      style={{
        width: "var(--sidebar-w)",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        backgroundColor: "var(--canvas)",
        borderRight: "1px solid var(--hairline)",
        padding: "24px 16px",
        userSelect: "none",
      }}
      aria-label="Primary Navigation"
    >
      {/* Brand Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "12px",
          padding: "0 8px 24px 8px",
          borderBottom: "1px solid var(--hairline)",
          marginBottom: "20px",
        }}
      >
        <div
          style={{
            width: "36px",
            height: "36px",
            borderRadius: "var(--r-md)",
            background: "var(--mat-ink)",
            boxShadow: "var(--raise-1)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--blue)",
          }}
        >
          <Layers size={20} strokeWidth={2.2} />
        </div>
        <div>
          <div
            style={{
              fontWeight: 700,
              fontSize: "15px",
              color: "var(--text-primary)",
              letterSpacing: "-0.02em",
            }}
          >
            ResearchMind
          </div>
          <div
            style={{
              fontSize: "11px",
              color: "var(--text-muted)",
              fontWeight: 500,
            }}
          >
            Universal Analyzer
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          gap: "6px",
        }}
      >
        <div
          style={{
            fontSize: "11px",
            fontWeight: 600,
            color: "var(--text-muted)",
            textTransform: "uppercase",
            letterSpacing: "0.04em",
            padding: "0 10px 4px 10px",
          }}
        >
          Workspace
        </div>
        {navItems.map((item) => {
          const isActive = currentPath === item.path;
          return (
            <button
              key={item.id}
              onClick={() => handleItemClick(item.path)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                width: "100%",
                padding: "10px 12px",
                borderRadius: "var(--r-md)",
                border: "none",
                background: isActive ? "var(--surface-soft)" : "transparent",
                boxShadow: isActive ? "var(--raise-1)" : "none",
                color: isActive
                  ? "var(--blue-action)"
                  : "var(--text-secondary)",
                fontWeight: isActive ? 600 : 500,
                fontSize: "14px",
                cursor: "pointer",
                textAlign: "left",
                transition: "all var(--dur-fast) var(--ease-out)",
                outline: "none",
              }}
              className="nav-link-btn"
            >
              <div
                style={{ display: "flex", alignItems: "center", gap: "10px" }}
              >
                <span
                  style={{
                    color: isActive ? "var(--blue-action)" : "var(--gray-500)",
                    display: "flex",
                  }}
                >
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <Badge variant={item.badgeVariant || "neutral"} size="sm">
                  {item.badge}
                </Badge>
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer Info Pill */}
      <div
        style={{
          marginTop: "auto",
          padding: "14px",
          borderRadius: "var(--r-lg)",
          background: "var(--surface-sunken)",
          boxShadow: "var(--inset-1)",
          display: "flex",
          flexDirection: "column",
          gap: "6px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            fontSize: "12px",
            fontWeight: 600,
            color: "var(--text-primary)",
          }}
        >
          <Sparkles size={14} color="var(--blue)" />
          <span>Local Mode Active</span>
        </div>
        <p
          style={{
            fontSize: "11px",
            color: "var(--text-secondary)",
            margin: 0,
            lineHeight: 1.4,
          }}
        >
          Single-user local demonstration with SQLite & MiniLM embedding.
        </p>
      </div>
    </aside>
  );
};
