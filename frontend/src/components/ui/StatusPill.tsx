import React from 'react';

export interface StatusPillProps {
  status: 'online' | 'degraded' | 'offline' | 'loading';
  label: string;
  sublabel?: string;
}

export const StatusPill: React.FC<StatusPillProps> = ({ status, label, sublabel }) => {
  const getColor = () => {
    switch (status) {
      case 'online':
        return 'var(--green-strong)';
      case 'degraded':
        return 'var(--orange-strong)';
      case 'offline':
        return 'var(--red-strong)';
      case 'loading':
      default:
        return 'var(--blue-action)';
    }
  };

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '8px',
        padding: '6px 14px',
        borderRadius: 'var(--r-pill)',
        background: 'var(--surface-soft)',
        boxShadow: 'var(--raise-1)',
        border: '1px solid rgba(255, 255, 255, 0.7)',
        fontSize: '12px',
        fontWeight: 500,
        color: 'var(--text-secondary)',
      }}
      role="status"
      aria-live="polite"
    >
      <span
        style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          backgroundColor: getColor(),
          display: 'inline-block',
          boxShadow: `0 0 8px ${getColor()}`,
          animation: status === 'loading' ? 'pulse 1.5s infinite' : 'none',
        }}
        aria-hidden="true"
      />
      <span>
        <strong>{label}</strong>
        {sublabel && <span style={{ color: 'var(--text-muted)', marginLeft: '4px' }}>· {sublabel}</span>}
      </span>
    </div>
  );
};
