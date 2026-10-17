export type MemoryType = "user" | "feedback" | "project" | "reference";
export type Scope = "global" | "here";

export interface Keyword { k: string; t: string }
export interface Similar { i: number; s: number }

export interface Memory {
  id: string;
  rel: string;
  path: string;
  hash: string;
  raw: string;
  meta: Record<string, unknown> & { name?: string; source?: Record<string, unknown> };
  body: string;
  description: string;
  type: MemoryType;
  scope: Scope;
  place: string;
  tool: string;
  host: string;
  created: string;
  updated: string;
  similar: Similar[];
  keywords: Keyword[];
  terms: string[];
  issues: string[];
}

export interface Place { key: string; count: number; ctx: Record<string, string> }

export interface Sync { remote: boolean; ahead?: number }

export interface State {
  generated: string;
  dataDir: string;
  memories: Memory[];
  method: string;
  semantic: boolean;
  places: Place[];
  stamp: string;
  sync: Sync;
}

export interface Commit { sha: string; date: string; subject: string; tool: string | null; added: number; changed: number; deleted: number }
export interface IndexPreview { text: string; chars: number; limit: number; global: number; here: number }
export interface Settings {
  version: string;
  dataDir: string;
  remote: string | null;
  sync: Sync;
  keywordStopwords: string[];
  model: { name: string; ready: boolean; dir: string; fetch: string; size: string };
  semantic: boolean;
}
export interface Check { ok: boolean; text: string }
