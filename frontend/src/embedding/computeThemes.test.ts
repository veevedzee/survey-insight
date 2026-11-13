import { describe, expect, it, vi } from "vitest";

const engine = vi.hoisted(() => ({ callEngine: vi.fn(), uploadToEngine: vi.fn() }));
vi.mock("../python/engine", () => engine);

import { computeThemes } from "./computeThemes";
import { describeProgress } from "./embeddings";

describe("computeThemes", () => {
  it("embeds each distinct answer once and sends vectors in each column's order", async () => {
    engine.callEngine.mockImplementation(async (_method: string, path: string, body?: string) => {
      if (path.endsWith("/texts")) {
        return {
          status: 200,
          body: {
            model: "Xenova/test-model",
            columns: [
              { column: "Q1", texts: ["bus", "exam"] },
              { column: "Q2", texts: ["exam", "gym"] },
            ],
          },
        };
      }
      return { status: 200, body: { posted: JSON.parse(body ?? "null") } };
    });
    const fakeEmbed = vi.fn(async (_model: string, texts: string[]) =>
      texts.map((t) => [t.length, 0]),
    );

    const result = (await computeThemes("abc", () => {}, fakeEmbed)) as unknown as {
      posted: unknown;
    };

    expect(fakeEmbed).toHaveBeenCalledWith("Xenova/test-model", ["bus", "exam", "gym"], expect.any(Function));
    expect(result.posted).toEqual({
      columns: [
        { column: "Q1", texts: ["bus", "exam"], vectors: [[3, 0], [4, 0]] },
        { column: "Q2", texts: ["exam", "gym"], vectors: [[4, 0], [3, 0]] },
      ],
    });
  });
});

describe("describeProgress", () => {
  it("explains the one-time download and the embedding count", () => {
    expect(describeProgress({ stage: "download", done: 60e6, total: 120e6 })).toMatch(
      /60 of 120 MB \(50%\)\. This happens only once/,
    );
    expect(describeProgress({ stage: "download", done: 135e6, total: 135e6 })).toBe(
      "Starting the language model…",
    );
    expect(describeProgress({ stage: "embed", done: 32, total: 230 })).toBe(
      "Reading answers on your device: 32 of 230",
    );
  });
});
