import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { useState } from "react";
import { MobileNav } from "../components/layout/MobileNav";
import { Topbar } from "../components/layout/Topbar";

const TestMobileNavWrapper = () => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div>
      <Topbar
        onOpenMobileNav={() => setIsOpen(true)}
        isMobileNavOpen={isOpen}
        readyStatus="online"
        readyData={null}
        configData={null}
        onRefreshStatus={vi.fn()}
        isRefreshing={false}
      />
      <MobileNav
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        currentPath="/dashboard"
        onNavigate={vi.fn()}
        triggerElement={
          typeof document !== "undefined"
            ? document.getElementById("mobile-nav-trigger")
            : null
        }
      />
    </div>
  );
};

describe("MobileNav Accessibility & Focus Management", () => {
  it("exposes aria-expanded and aria-controls on trigger button", () => {
    const { container } = render(<TestMobileNavWrapper />);
    const trigger = container.querySelector(
      "#mobile-nav-trigger",
    ) as HTMLButtonElement;
    expect(trigger).not.toBeNull();
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).toHaveAttribute("aria-controls", "mobile-nav-drawer");
  });

  it("opens drawer, exposes dialog role, traps focus, and closes on Escape", async () => {
    const { container } = render(<TestMobileNavWrapper />);
    const trigger = container.querySelector(
      "#mobile-nav-trigger",
    ) as HTMLButtonElement;

    // Focus trigger and open
    trigger.focus();
    fireEvent.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");

    const dialog = screen.getByRole("dialog", {
      name: /Mobile Navigation Drawer/i,
    });
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-modal", "true");

    const closeBtn = screen.getByRole("button", { name: /Close navigation/i });

    // Close button should receive focus
    await waitFor(() => {
      expect(document.activeElement).toBe(closeBtn);
    });

    // Test Escape key closes drawer
    fireEvent.keyDown(window, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(trigger).toHaveAttribute("aria-expanded", "false");
      // Focus restored to trigger
      expect(document.activeElement).toBe(trigger);
    });
  });

  it("traps tab focus inside the modal drawer", async () => {
    const { container } = render(<TestMobileNavWrapper />);
    const trigger = container.querySelector(
      "#mobile-nav-trigger",
    ) as HTMLButtonElement;
    fireEvent.click(trigger);

    const dialog = screen.getByRole("dialog");
    const focusable = dialog.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    expect(focusable.length).toBeGreaterThan(1);

    const firstElement = focusable[0];
    const lastElement = focusable[focusable.length - 1];

    // Focus first element, press Shift+Tab -> should wrap to last element
    firstElement.focus();
    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(lastElement);

    // Focus last element, press Tab -> should wrap to first element
    lastElement.focus();
    fireEvent.keyDown(window, { key: "Tab", shiftKey: false });
    expect(document.activeElement).toBe(firstElement);
  });
});
