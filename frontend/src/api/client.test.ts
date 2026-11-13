import { describe, expect, it, vi } from "vitest";

const engine = vi.hoisted(() => ({
  callEngine: vi.fn(),
  uploadToEngine: vi.fn(),
}));
vi.mock("../python/engine", () => engine);

import { ApiError, confirmColumns, deleteSession, downloadCleanedCsv } from "./client";

describe("client in browser mode", () => {
  it("routes calls to the Python engine with the same paths as the HTTP API", async () => {
    engine.callEngine.mockResolvedValueOnce({ status: 200, body: { total_masked: 5 } });
    const report = await confirmColumns("abc", { Age: "numeric" });
    expect(engine.callEngine).toHaveBeenCalledWith(
      "POST",
      "/api/sessions/abc/columns",
      JSON.stringify({ types: { Age: "numeric" } }),
    );
    expect(report).toEqual({ total_masked: 5 });
  });

  it("turns engine errors into ApiError with the status code", async () => {
    engine.callEngine.mockResolvedValueOnce({ status: 404, body: { detail: "This session has expired." } });
    await expect(deleteSession("abc")).rejects.toEqual(new ApiError("This session has expired.", 404));
  });

  it("builds the CSV download from the engine's text", async () => {
    engine.callEngine.mockResolvedValueOnce({
      status: 200,
      body: { filename: "s-cleaned.csv", content: "﻿Q\nموافق\n" },
    });
    const { blob, filename } = await downloadCleanedCsv("abc");
    expect(filename).toBe("s-cleaned.csv");
    expect(blob.type).toBe("text/csv;charset=utf-8");
    const bytes = new Uint8Array(await blob.arrayBuffer());
    expect([...bytes.slice(0, 3)]).toEqual([0xef, 0xbb, 0xbf]); // UTF-8 byte-order mark
  });
});
