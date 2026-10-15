import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import { Sidebar } from './Sidebar';

interface MobileNavProps {
  isOpen: boolean;
  onClose: () => void;
  currentPath: string;
  onNavigate: (path: string) => void;
}

export const MobileNav: React.FC<MobileNavProps> = ({
  isOpen,
  onClose,
  currentPath,
  onNavigate,
}) => {
  // Handle Escape key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Lock body scroll when mobile nav is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 100,
        display: 'flex',
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Mobile Navigation Drawer"
    >
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: 'var(--scrim)',
          backdropFilter: 'blur(4px)',
          WebkitBackdropFilter: 'blur(4px)',
          animation: 'fadeIn var(--dur-fast) var(--ease-out)',
        }}
        aria-hidden="true"
      />

      {/* Drawer Content */}
      <div
        style={{
          position: 'relative',
          width: '85%',
          maxWidth: '300px',
          height: '100%',
          backgroundColor: 'var(--canvas)',
          boxShadow: 'var(--float-3)',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 101,
          animation: 'slideInLeft var(--dur-base) var(--ease-sheet)',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: '16px',
            right: '16px',
            zIndex: 102,
          }}
        >
          <button
            onClick={onClose}
            style={{
              background: 'var(--surface-soft)',
              border: 'none',
              borderRadius: '50%',
              width: '32px',
              height: '32px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: 'var(--raise-1)',
              cursor: 'pointer',
              color: 'var(--text-secondary)',
            }}
            aria-label="Close navigation"
          >
            <X size={18} />
          </button>
        </div>

        <Sidebar
          currentPath={currentPath}
          onNavigate={onNavigate}
          onCloseMobile={onClose}
        />
      </div>
    </div>
  );
};
