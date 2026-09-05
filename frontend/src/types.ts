/** Shared API types for the Quranic Shazam frontend. */

export interface ReciterMatch {
  reciter: string;
  display?: string;
  score: number;
}

export interface IdentifyResponse {
  matches: ReciterMatch[];
}

export interface ApiError {
  detail?: string;
  error?: string;
}
