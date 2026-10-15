import React from 'react';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'raised' | 'flat' | 'sunken';
  elevation?: 1 | 2 | 3;
}

export const Card: React.FC<CardProps> = ({
  children,
  variant = 'raised',
  elevation = 1,
  style,
  className = '',
  ...props
}) => {
  const getStyles = (): React.CSSProperties => {
    if (variant === 'sunken') {
      return {
        background: 'var(--surface-sunken)',
        boxShadow: 'var(--inset-1)',
        border: '1px solid var(--hairline)',
      };
    }
    if (variant === 'flat') {
      return {
        background: 'var(--surface)',
        border: '1px solid var(--border-strong)',
      };
    }
    // Raised (default Apple Modern Soft-Raised)
    return {
      background: 'var(--surface-soft)',
      boxShadow: elevation === 2 ? 'var(--raise-2)' : elevation === 3 ? 'var(--raise-3)' : 'var(--raise-1)',
      border: '1px solid rgba(255, 255, 255, 0.8)',
    };
  };

  return (
    <div
      style={{
        borderRadius: 'var(--r-xl)',
        padding: '24px',
        transition: 'transform var(--dur-base) var(--ease-out), box-shadow var(--dur-base) var(--ease-out)',
        ...getStyles(),
        ...style,
      }}
      className={`card-${variant} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};
