import React, { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { Sidebar } from "./Sidebar";

interface MobileNavProps {
  isOpen: boolean;
  onClose: () => void;
  currentPath: string;
  onNavigate: (path: string) => void;
  triggerElement?: HTMLElement | null;
}

export const MobileNav: React.FC<MobileNavProps> = ({
  isOpen,
  onClose,
  currentPath,
  onNavigate,
  triggerElement,
}) => {
  const drawerRef = useRef<HTMLDivElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const previousActiveElement = useRef<HTMLElement | null>(null);

  // Focus management: capture previous active element, focus drawer close button on open, restore on close
  useEffect(() => {
    if (isOpen) {
      previousActiveElement.current =
        triggerElement ||
        (typeof document !== "undefined"
          ? (document.getElementById("mobile-nav-trigger") as HTMLElement)
          : null) ||
        (document.activeElement as HTMLElement | null);
      requestAnimationFrame(() => {
        closeButtonRef.current?.focus();
      });
    } else {
      const el =
        previousActiveElement.current ||
        (typeof document !== "undefined"
          ? (document.getElementById("mobile-nav-trigger") as HTMLElement)
          : null);
      if (el && typeof el.focus === "function") {
        el.focus();
      }
    }
  }, [isOpen, triggerElement]);

  // Focus trap inside drawer
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key === "Tab" && drawerRef.current) {
        const focusableElements =
          drawerRef.current.querySelectorAll<HTMLElement>(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
          );
        if (focusableElements.length === 0) return;

        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === firstElement) {
            e.preventDefault();
            lastElement.focus();
          }
        } else {
          if (document.activeElement === lastElement) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Lock body scroll when mobile nav is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      id="mobile-nav-drawer"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        display: "flex",
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Mobile Navigation Drawer"
    >
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          backgroundColor: "var(--scrim)",
          backdropFilter: "blur(4px)",
          WebkitBackdropFilter: "blur(4px)",
          animation: "fadeIn var(--dur-fast) var(--ease-out)",
        }}
        aria-hidden="true"
      />

      {/* Drawer Content */}
      <div
        ref={drawerRef}
        style={{
          position: "relative",
          width: "85%",
          maxWidth: "300px",
          height: "100%",
          backgroundColor: "var(--canvas)",
          boxShadow: "var(--float-3)",
          display: "flex",
          flexDirection: "column",
          zIndex: 101,
          animation: "slideInLeft var(--dur-base) var(--ease-sheet)",
        }}
      >
        <div
          style={{
            position: "absolute",
            top: "16px",
            right: "16px",
            zIndex: 102,
          }}
        >
          <button
            ref={closeButtonRef}
            onClick={onClose}
            style={{
              background: "var(--surface-soft)",
              border: "none",
              borderRadius: "50%",
              width: "32px",
              height: "32px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "var(--raise-1)",
              cursor: "pointer",
              color: "var(--text-secondary)",
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
