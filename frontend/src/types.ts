/** Shared API types for the Quranic Shazam frontend. */

export interface ReciterMatch {
  reciter: string;
  display?: string;
  score: number;
}

export interface IdentifyResponse {
  matches: ReciterMatch[];
}

export interface VerseMatch {
  surah: number;
  surah_name?: string | null;
  ayah_start: number;
  ayah_end: number;
  score: number;
  words_matched: number;
  words_total: number;
  text?: string | null;
}

export interface IdentifyVerseResponse {
  transcript?: string | null;
  confident: boolean;
  needs_more_audio?: boolean;
  listen_limit_reached?: boolean;
  audio_seconds?: number | null;
  matches: VerseMatch[];
}

export interface ApiError {
  detail?: string;
  error?: string;
}
