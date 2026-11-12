// The three-step themes flow: ask the server which answers to embed, embed
// them in the browser, send the vectors back for clustering and labelling.
import { getTextsToEmbed, postThemes } from "../api/client";
import type { EmbeddedColumn, ThemesReport } from "../api/types";
import { embedTexts, type EmbedProgress } from "./embeddings";

type Embed = typeof embedTexts;

export async function computeThemes(
  sessionId: string,
  onProgress: (progress: EmbedProgress) => void,
  embed: Embed = embedTexts, // injectable for tests
): Promise<ThemesReport> {
  const { model, columns } = await getTextsToEmbed(sessionId);
  // Embed every distinct answer once, even if it appears in two columns.
  const unique = [...new Set(columns.flatMap((c) => c.texts))];
  const vectors = await embed(model, unique, onProgress);
  const byText = new Map(unique.map((t, i) => [t, vectors[i]]));
  const embedded: EmbeddedColumn[] = columns.map((c) => ({
    column: c.column,
    texts: c.texts,
    vectors: c.texts.map((t) => byText.get(t) as number[]),
  }));
  return postThemes(sessionId, embedded);
}
