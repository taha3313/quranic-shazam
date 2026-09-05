/** Centralized backend communication (REST + WebSocket URL builders). */

import type { IdentifyResponse } from './types';

const rawApiUrl = import.meta.env.VITE_API_URL as string | undefined;
const rawWsUrl = import.meta.env.VITE_WS_URL as string | undefined;

export const API_BASE_URL: string =
  rawApiUrl ?? 'http://127.0.0.1:8000';

function defaultWsUrl(): string {
  try {
    const url = new URL(API_BASE_URL);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return url.origin;
  } catch {
    return 'ws://127.0.0.1:8000';
  }
}

export const WS_BASE_URL: string = rawWsUrl ?? defaultWsUrl();

export const IDENTIFY_URL = `${API_BASE_URL}/identify_reciter`;
export const LIVE_WS_URL = `${WS_BASE_URL}/live_reciter`;

export async function identifyReciter(
  audio: File | Blob,
  filename = 'recording.wav',
  topK = 3,
): Promise<IdentifyResponse> {
  const formData = new FormData();
  const file = audio instanceof File ? audio : new File([audio], filename);
  formData.append('file', file);

  const response = await fetch(
    `${IDENTIFY_URL}?top_k=${encodeURIComponent(String(topK))}`,
    { method: 'POST', body: formData },
  );

  if (!response.ok) {
    let detail = 'Identification failed';
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* keep generic message */
    }
    throw new Error(detail);
  }

  return (await response.json()) as IdentifyResponse;
}
