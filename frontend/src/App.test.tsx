import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "./App";

// The real engine runs Python in a Web Worker, which jsdom doesn't have.
const status = vi.hoisted(() => ({
  current: { stage: "loading", message: "Loading…", progress: 0.3 } as {
    stage: string;
    message: string;
    progress: number | null;
  },
}));
vi.mock("./python/engine", () => ({
  startEngine: vi.fn(),
  useEngineStatus: () => status.current,
  callEngine: vi.fn(),
  uploadToEngine: vi.fn(),
}));

describe("App (in-browser mode)", () => {
  it("shows the engine loading, then ready", () => {
    const { rerender } = render(<App />);
    expect(screen.getByText(/Loading engine… 30%/)).toBeInTheDocument();
    expect(screen.getByText(/first visit downloads Python/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try with sample data" })).toBeInTheDocument();

    status.current = { stage: "ready", message: "Ready", progress: 1 };
    rerender(<App />);
    expect(screen.getByText(/Runs on your device/)).toBeInTheDocument();
    expect(screen.getByText("Never leaves your device")).toBeInTheDocument();
  });

  it("explains when the engine can't load", () => {
    status.current = { stage: "error", message: "network down", progress: null };
    render(<App />);
    expect(screen.getByText(/Engine failed to load/)).toBeInTheDocument();
    expect(screen.getByText(/couldn't load \(network down\)/)).toBeInTheDocument();
  });
});
