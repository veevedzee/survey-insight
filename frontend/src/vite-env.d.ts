/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the deployed backend, e.g. https://you-survey-insight.hf.space. Empty in dev. */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
