import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

function mockFetch(response: Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(() => response));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("shows the backend version when the health check succeeds", async () => {
    mockFetch(Promise.resolve(new Response(JSON.stringify({ status: "ok", version: "9.9.9" }))));
    render(<App />);
    expect(await screen.findByText(/Backend connected · v9.9.9/)).toBeInTheDocument();
  });

  it("says the backend is unreachable when the request fails", async () => {
    mockFetch(Promise.reject(new TypeError("Failed to fetch")));
    render(<App />);
    expect(await screen.findByText(/Backend unreachable/)).toBeInTheDocument();
  });
});
