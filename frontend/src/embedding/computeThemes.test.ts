import { afterEach, describe, expect, it, vi } from "vitest";
import { computeThemes } from "./computeThemes";
import { describeProgress } from "./embeddings";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("computeThemes", () => {
  it("embeds each distinct answer once and sends vectors in each column's order", async () => {
    const posted: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.endsWith("/texts")) {
          return new Response(
            JSON.stringify({
              model: "Xenova/test-model",
              columns: [
                { column: "Q1", texts: ["bus", "exam"] },
                { column: "Q2", texts: ["exam", "gym"] },
              ],
            }),
          );
        }
        posted.push(JSON.parse(String(init?.body)));
        return new Response(JSON.stringify({ model: "m", columns: [], sentiment_note: "" }));
      }),
    );
    const fakeEmbed = vi.fn(async (_model: string, texts: string[]) =>
      texts.map((t) => [t.length, 0]),
    );

    await computeThemes("abc", () => {}, fakeEmbed);

    expect(fakeEmbed).toHaveBeenCalledWith("Xenova/test-model", ["bus", "exam", "gym"], expect.any(Function));
    expect(posted[0]).toEqual({
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
