import React, { useState, useEffect, useCallback } from "react";
import { AppShell } from "../components/layout/AppShell";
import { LandingPage } from "../pages/LandingPage";
import { DashboardPage } from "../pages/DashboardPage";
import { LibraryPage } from "../pages/LibraryPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { api, ApiClientError } from "../api/client";
import { ReadyResponse, PublicConfigResponse } from "../api/types";
import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "../components/ui/Button";

export const App: React.FC = () => {
  // Simple client-side route tracking
  const [currentPath, setCurrentPath] = useState<string>(() => {
    return window.location.pathname || "/";
  });

  // Backend connection state
  const [readyStatus, setReadyStatus] = useState<
    "online" | "degraded" | "offline" | "loading"
  >("loading");
  const [readyData, setReadyData] = useState<ReadyResponse | null>(null);
  const [configData, setConfigData] = useState<PublicConfigResponse | null>(
    null,
  );
  const [apiError, setApiError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const fetchBackendStatus = useCallback(async () => {
    setIsRefreshing(true);
    setApiError(null);
    try {
      const [readyRes, configRes] = await Promise.all([
        api.getReady(),
        api.getPublicConfig(),
      ]);
      setReadyData(readyRes);
      setConfigData(configRes);
      setReadyStatus(readyRes.status === "ready" ? "online" : "degraded");
    } catch (err: any) {
      setReadyStatus("offline");
      if (err instanceof ApiClientError) {
        setApiError(`${err.code}: ${err.message}`);
      } else {
        setApiError("Unable to connect to the backend server.");
      }
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchBackendStatus();

    // Listen for browser back/forward buttons
    const handlePopState = () => {
      setCurrentPath(window.location.pathname || "/");
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [fetchBackendStatus]);

  const handleNavigate = (path: string) => {
    setCurrentPath(path);
    window.history.pushState({}, "", path);
    window.scrollTo(0, 0);
  };

  // Render view according to path
  const renderCurrentView = () => {
    switch (currentPath) {
      case "/":
        return (
          <LandingPage onOpenWorkspace={() => handleNavigate("/dashboard")} />
        );
      case "/dashboard":
        return (
          <DashboardPage
            onNavigateToLibrary={() => handleNavigate("/library")}
            readyStatus={readyStatus}
            readyData={readyData}
            configData={configData}
          />
        );
      case "/library":
        return <LibraryPage />;
      default:
        return <NotFoundPage onGoHome={() => handleNavigate("/dashboard")} />;
    }
  };

  return (
    <AppShell
      currentPath={currentPath}
      onNavigate={handleNavigate}
      readyStatus={readyStatus}
      readyData={readyData}
      configData={configData}
      onRefreshStatus={fetchBackendStatus}
      isRefreshing={isRefreshing}
    >
      {/* Offline Alert Banner if backend is not reachable */}
      {readyStatus === "offline" && (
        <div
          className="offline-banner"
          style={{
            marginBottom: "24px",
            padding: "14px 20px",
            borderRadius: "var(--r-lg)",
            background: "var(--red-surface)",
            border: "1px solid rgba(255, 59, 48, 0.3)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "12px",
          }}
          role="alert"
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <AlertCircle size={18} color="var(--red-strong)" />
            <span
              style={{
                fontSize: "13px",
                color: "var(--red-text)",
                fontWeight: 600,
              }}
            >
              Backend Connection Error:{" "}
              {apiError ||
                "API server is not responding at http://127.0.0.1:8000."}
            </span>
          </div>
          <Button
            variant="soft"
            size="sm"
            onClick={fetchBackendStatus}
            isLoading={isRefreshing}
            style={{ fontSize: "12px" }}
          >
            <RefreshCw size={12} />
            <span>Retry Connection</span>
          </Button>
        </div>
      )}

      {renderCurrentView()}
    </AppShell>
  );
};
