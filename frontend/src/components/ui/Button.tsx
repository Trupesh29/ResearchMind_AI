import React from "react";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "ink" | "soft" | "blue" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  isLoading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = "ink",
  size = "md",
  isLoading = false,
  disabled,
  style,
  className = "",
  ...props
}) => {
  const getVariantStyles = (): React.CSSProperties => {
    switch (variant) {
      case "ink":
        return {
          background: "var(--mat-ink)",
          color: "var(--text-inverse)",
          boxShadow: "var(--raise-1)",
          border: "1px solid rgba(255,255,255,0.1)",
        };
      case "soft":
        return {
          background: "var(--surface-soft)",
          color: "var(--text-primary)",
          boxShadow: "var(--raise-1)",
          border: "1px solid var(--hairline)",
        };
      case "blue":
        return {
          background: "var(--blue-action)",
          color: "var(--text-inverse)",
          boxShadow: "var(--raise-1)",
          border: "none",
        };
      case "danger":
        return {
          background: "var(--red-strong)",
          color: "var(--text-inverse)",
          boxShadow: "var(--raise-1)",
          border: "none",
        };
      case "ghost":
        return {
          background: "transparent",
          color: "var(--text-secondary)",
          border: "none",
        };
    }
  };

  const getSizeStyles = (): React.CSSProperties => {
    switch (size) {
      case "sm":
        return {
          padding: "6px 14px",
          fontSize: "13px",
          height: "32px",
        };
      case "lg":
        return {
          padding: "12px 28px",
          fontSize: "16px",
          height: "48px",
        };
      case "md":
      default:
        return {
          padding: "9px 20px",
          fontSize: "14px",
          height: "40px",
        };
    }
  };

  return (
    <button
      disabled={disabled || isLoading}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "8px",
        fontWeight: 600,
        borderRadius: "var(--r-pill)",
        cursor: disabled || isLoading ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        transition: "all var(--dur-fast) var(--ease-out)",
        whiteSpace: "nowrap",
        outline: "none",
        ...getVariantStyles(),
        ...getSizeStyles(),
        ...style,
      }}
      className={`btn-${variant} ${className}`}
      {...props}
    >
      {isLoading && (
        <span
          style={{
            display: "inline-block",
            width: "14px",
            height: "14px",
            border: "2px solid currentColor",
            borderRightColor: "transparent",
            borderRadius: "50%",
            animation: "spin 0.6s linear infinite",
          }}
        />
      )}
      {children}
    </button>
  );
};
