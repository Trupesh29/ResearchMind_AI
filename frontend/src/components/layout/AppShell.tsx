import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
import { MobileNav } from './MobileNav';
import { ReadyResponse, PublicConfigResponse } from '../../api/types';

interface AppShellProps {
  children: React.ReactNode;
  currentPath: string;
  onNavigate: (path: string) => void;
  readyStatus: 'online' | 'degraded' | 'offline' | 'loading';
  readyData: ReadyResponse | null;
  configData: PublicConfigResponse | null;
  onRefreshStatus: () => void;
  isRefreshing: boolean;
}

export const AppShell: React.FC<AppShellProps> = ({
  children,
  currentPath,
  onNavigate,
  readyStatus,
  readyData,
  configData,
  onRefreshStatus,
  isRefreshing,
}) => {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--canvas)' }}>
      {/* Accessibility Skip Link */}
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      {/* Desktop Sidebar */}
      <div className="desktop-sidebar" style={{ height: '100vh', position: 'sticky', top: 0 }}>
        <Sidebar currentPath={currentPath} onNavigate={onNavigate} />
      </div>

      {/* Mobile Drawer */}
      <MobileNav
        isOpen={mobileNavOpen}
        onClose={() => setMobileNavOpen(false)}
        currentPath={currentPath}
        onNavigate={onNavigate}
      />

      {/* Main Content Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <Topbar
          onOpenMobileNav={() => setMobileNavOpen(true)}
          readyStatus={readyStatus}
          readyData={readyData}
          configData={configData}
          onRefreshStatus={onRefreshStatus}
          isRefreshing={isRefreshing}
        />

        <main
          id="main-content"
          tabIndex={-1}
          style={{
            flex: 1,
            padding: '32px 24px',
            outline: 'none',
          }}
        >
          <div className="container">{children}</div>
        </main>
      </div>
    </div>
  );
};
