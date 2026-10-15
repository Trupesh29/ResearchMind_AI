import React from 'react';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'neutral' | 'info' | 'success' | 'warning' | 'error';
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'md',
  style,
  className = '',
  ...props
}) => {
  const getVariantStyles = (): React.CSSProperties => {
    switch (variant) {
      case 'info':
        return {
          background: 'var(--blue-surface)',
          color: 'var(--blue-on-surface)',
          border: '1px solid rgba(0, 122, 255, 0.2)',
        };
      case 'success':
        return {
          background: 'var(--green-surface)',
          color: 'var(--green-text)',
          border: '1px solid rgba(52, 199, 89, 0.2)',
        };
      case 'warning':
        return {
          background: 'var(--orange-surface)',
          color: 'var(--orange-text)',
          border: '1px solid rgba(255, 149, 0, 0.2)',
        };
      case 'error':
        return {
          background: 'var(--red-surface)',
          color: 'var(--red-text)',
          border: '1px solid rgba(255, 59, 48, 0.2)',
        };
      case 'neutral':
      default:
        return {
          background: 'var(--surface-sunken)',
          color: 'var(--text-muted)',
          border: '1px solid var(--hairline)',
        };
    }
  };

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '5px',
        fontWeight: 600,
        borderRadius: 'var(--r-pill)',
        fontSize: size === 'sm' ? '11px' : '12px',
        padding: size === 'sm' ? '2px 8px' : '4px 12px',
        letterSpacing: '-0.01em',
        ...getVariantStyles(),
        ...style,
      }}
      className={`badge-${variant} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
};
