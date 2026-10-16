import React from "react";
import { Menu, Folder, User as UserIcon, RefreshCw } from "lucide-react";
import { StatusPill } from "../ui/StatusPill";
import { ReadyResponse, PublicConfigResponse } from "../../api/types";

interface TopbarProps {
  onOpenMobileNav: () => void;
  isMobileNavOpen?: boolean;
  readyStatus: "online" | "degraded" | "offline" | "loading";
  readyData: ReadyResponse | null;
  configData: PublicConfigResponse | null;
  onRefreshStatus: () => void;
  isRefreshing: boolean;
}

export const Topbar: React.FC<TopbarProps> = ({
  onOpenMobileNav,
  isMobileNavOpen = false,
  readyStatus,
  readyData,
  configData,
  onRefreshStatus,
  isRefreshing,
}) => {
  return (
    <header
      className="topbar-header"
      style={{
        height: "var(--nav-h)",
        backgroundColor: "var(--glass-nav)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        borderBottom: "1px solid var(--hairline)",
        padding: "0 24px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        position: "sticky",
        top: 0,
        zIndex: 40,
      }}
    >
      {/* Left: Mobile Toggle + Workspace Indicator */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "12px",
          minWidth: 0,
        }}
      >
        <button
          id="mobile-nav-trigger"
          onClick={onOpenMobileNav}
          className="mobile-menu-btn"
          aria-expanded={isMobileNavOpen}
          aria-controls="mobile-nav-drawer"
          aria-label="Open mobile navigation menu"
          style={{
            background: "var(--surface-soft)",
            border: "none",
            boxShadow: "var(--raise-1)",
            padding: "8px",
            borderRadius: "var(--r-md)",
            cursor: "pointer",
            color: "var(--text-primary)",
            flexShrink: 0,
          }}
        >
          <Menu size={20} />
        </button>

        <div
          className="topbar-workspace-pill"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "6px 14px",
            borderRadius: "var(--r-pill)",
            background: "var(--surface-soft)",
            boxShadow: "var(--raise-1)",
            border: "1px solid rgba(255, 255, 255, 0.7)",
            fontSize: "13px",
            fontWeight: 600,
            color: "var(--text-primary)",
            minWidth: 0,
          }}
        >
          <Folder
            size={15}
            color="var(--blue-action)"
            style={{ flexShrink: 0 }}
          />
          <span
            className="topbar-workspace-name"
            style={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {configData?.default_user?.display_name
              ? `${configData.default_user.display_name} Workspace (Local)`
              : "Local Workspace (Pending Setup)"}
          </span>
        </div>
      </div>

      {/* Right: Live Health + User Identity */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          flexShrink: 0,
        }}
      >
        <button
          onClick={onRefreshStatus}
          disabled={isRefreshing}
          style={{
            background: "transparent",
            border: "none",
            color: "var(--text-muted)",
            cursor: isRefreshing ? "wait" : "pointer",
            padding: "6px",
            borderRadius: "var(--r-pill)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transition: "color var(--dur-fast) var(--ease-out)",
          }}
          title="Refresh backend status"
          aria-label="Refresh backend status"
        >
          <RefreshCw
            size={16}
            style={{
              animation: isRefreshing ? "spin 1s linear infinite" : "none",
            }}
          />
        </button>

        <StatusPill
          status={readyStatus}
          label={
            readyStatus === "online"
              ? "Backend Connected"
              : readyStatus === "loading"
                ? "Connecting..."
                : "Backend Offline"
          }
          sublabel={
            readyData?.checks.database?.status === "healthy"
              ? "SQLite Ready"
              : undefined
          }
        />

        <div
          className="topbar-user-pill"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "6px 12px",
            borderRadius: "var(--r-pill)",
            background: "var(--surface-soft)",
            boxShadow: "var(--raise-1)",
            fontSize: "13px",
            fontWeight: 500,
            color: "var(--text-primary)",
          }}
        >
          <div
            style={{
              width: "22px",
              height: "22px",
              borderRadius: "50%",
              background: "var(--mat-ink)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--text-inverse)",
              flexShrink: 0,
            }}
          >
            <UserIcon size={12} />
          </div>
          <span
            className="topbar-user-name"
            style={{ fontSize: "12px", fontWeight: 600 }}
          >
            {configData?.default_user.display_name || "Local User"}
          </span>
        </div>
      </div>
    </header>
  );
};
