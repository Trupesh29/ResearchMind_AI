import React from 'react';
import { Menu, Folder, User as UserIcon, RefreshCw } from 'lucide-react';
import { StatusPill } from '../ui/StatusPill';
import { ReadyResponse, PublicConfigResponse } from '../../api/types';

interface TopbarProps {
  onOpenMobileNav: () => void;
  readyStatus: 'online' | 'degraded' | 'offline' | 'loading';
  readyData: ReadyResponse | null;
  configData: PublicConfigResponse | null;
  onRefreshStatus: () => void;
  isRefreshing: boolean;
}

export const Topbar: React.FC<TopbarProps> = ({
  onOpenMobileNav,
  readyStatus,
  readyData,
  configData,
  onRefreshStatus,
  isRefreshing,
}) => {
  return (
    <header
      style={{
        height: 'var(--nav-h)',
        backgroundColor: 'var(--glass-nav)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderBottom: '1px solid var(--hairline)',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky',
        top: 0,
        zIndex: 40,
      }}
    >
      {/* Left: Mobile Toggle + Workspace Indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <button
          onClick={onOpenMobileNav}
          className="mobile-menu-btn"
          style={{
            display: 'none',
            background: 'var(--surface-soft)',
            border: 'none',
            boxShadow: 'var(--raise-1)',
            padding: '8px',
            borderRadius: 'var(--r-md)',
            cursor: 'pointer',
            color: 'var(--text-primary)',
          }}
          aria-label="Open mobile navigation menu"
        >
          <Menu size={20} />
        </button>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 14px',
            borderRadius: 'var(--r-pill)',
            background: 'var(--surface-soft)',
            boxShadow: 'var(--raise-1)',
            border: '1px solid rgba(255, 255, 255, 0.7)',
            fontSize: '13px',
            fontWeight: 600,
            color: 'var(--text-primary)',
          }}
        >
          <Folder size={15} color="var(--blue-action)" />
          <span>Default Workspace</span>
        </div>
      </div>

      {/* Right: Live Health + User Identity */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <button
          onClick={onRefreshStatus}
          disabled={isRefreshing}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: isRefreshing ? 'wait' : 'pointer',
            padding: '6px',
            borderRadius: 'var(--r-pill)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'color var(--dur-fast) var(--ease-out)',
          }}
          title="Refresh backend status"
          aria-label="Refresh backend status"
        >
          <RefreshCw
            size={16}
            style={{
              animation: isRefreshing ? 'spin 1s linear infinite' : 'none',
            }}
          />
        </button>

        <StatusPill
          status={readyStatus}
          label={
            readyStatus === 'online'
              ? 'Backend Connected'
              : readyStatus === 'loading'
              ? 'Connecting...'
              : 'Backend Offline'
          }
          sublabel={readyData?.checks.database === 'connected' ? 'SQLite Ready' : undefined}
        />

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 12px',
            borderRadius: 'var(--r-pill)',
            background: 'var(--surface-soft)',
            boxShadow: 'var(--raise-1)',
            fontSize: '13px',
            fontWeight: 500,
            color: 'var(--text-primary)',
          }}
        >
          <div
            style={{
              width: '22px',
              height: '22px',
              borderRadius: '50%',
              background: 'var(--mat-ink)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-inverse)',
            }}
          >
            <UserIcon size={12} />
          </div>
          <span style={{ fontSize: '12px', fontWeight: 600 }}>
            {configData?.default_user.display_name || 'Local User'}
          </span>
        </div>
      </div>
    </header>
  );
};
