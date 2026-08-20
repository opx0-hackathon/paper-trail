export type StampKind = "value" | "proof" | "refused";

export interface Stamp {
  path: string;
  note: string;
  purpose: string;
  kind: StampKind;
  reason: string;
}

export interface Memory {
  path: string;
  note: string;
  value: string;
  attested: boolean;
  sensitive: boolean;
  revoked: boolean;
  source: string;
}

export interface Receipt {
  action: string;
  path: string;
  purpose: string;
  detail: string;
  created_at: number;
}

export interface Ask {
  path: string;
  note: string;
  purpose: string;
  sensitive: boolean;
}

export interface Proposal {
  question: string;
  ordinary: Ask[];
  special: Ask[];
  cached: boolean;
}

export interface Suggestion {
  path: string;
  value: string;
  note: string;
}

export interface Candidate {
  path: string;
  value: string;
  note: string;
  attested: boolean;
  sensitive: boolean;
}

export interface Share {
  token: string;
  paths: string[];
  created_at: number;
  expires_at: number;
  views: number;
  revoked: boolean;
}

export interface Grant {
  id: string;
  app: string;
  paths: string[];
  created_at: number;
  expires_at: number;
  reads: number;
  revoked: boolean;
}

export interface PendingRequest {
  id: string;
  app: string;
  paths: string[];
  purpose: string;
  created_at: number;
}

export interface FileState {
  holder: string;
  starters: string[];
  live: boolean;
  model: string;
  memories: Memory[];
  receipts: Receipt[];
  shares: Share[];
  grants: Grant[];
  pending: PendingRequest[];
}

export interface AnswerPayload extends FileState {
  answer: string;
  stamps: Stamp[];
  model: string;
  cached: boolean;
  suggestion: Suggestion | null;
  notice?: string;
}

export interface ProposalPayload extends FileState {
  proposal: Proposal;
  notice?: string;
}

export interface ImportPayload extends FileState {
  candidates: Candidate[];
  notice?: string;
}
