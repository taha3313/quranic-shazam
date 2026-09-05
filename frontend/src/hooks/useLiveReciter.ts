import { useCallback, useEffect, useRef, useState } from 'react';
import { LIVE_WS_URL } from '../api';
import type { IdentifyResponse } from '../types';

interface UseLiveReciter {
  isRecording: boolean;
  liveResult: IdentifyResponse | null;
  error: string | null;
  start: () => Promise<void>;
  stop: () => void;
}

/**
 * Encapsulates microphone recording + live WebSocket recognition.
 * Streams webm/opus chunks to the backend and surfaces predictions.
 */
export function useLiveReciter(): UseLiveReciter {
  const [isRecording, setIsRecording] = useState(false);
  const [liveResult, setLiveResult] = useState<IdentifyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const recordingRef = useRef(false);

  const cleanup = useCallback(() => {
    recordingRef.current = false;
    try {
      mediaRecorderRef.current?.stop();
    } catch {
      /* already stopped */
    }
    mediaRecorderRef.current = null;
    try {
      wsRef.current?.close();
    } catch {
      /* already closed */
    }
    wsRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => cleanup, [cleanup]);

  const start = useCallback(async () => {
    setError(null);
    setLiveResult(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const ws = new WebSocket(LIVE_WS_URL);
      wsRef.current = ws;
      ws.onopen = () => console.log('Live WebSocket connected.');
      ws.onerror = () => setError('Live connection error.');
      ws.onclose = () => console.log('Live WebSocket closed.');
      ws.onmessage = (event: MessageEvent<string>) => {
        try {
          const data = JSON.parse(event.data) as IdentifyResponse & { error?: string };
          if (data.error) {
            setError(data.error);
            return;
          }
          setLiveResult(data);
        } catch {
          setError('Received invalid live response.');
        }
      };

      const recorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus',
      });
      mediaRecorderRef.current = recorder;
      recordingRef.current = true;
      setIsRecording(true);

      recorder.start(300);

      recorder.ondataavailable = (event: BlobEvent) => {
        if (!recordingRef.current) return;
        if (event.data && event.data.size > 0 && ws.readyState === WebSocket.OPEN) {
          void event.data
            .arrayBuffer()
            .then((buf) => ws.send(buf))
            .catch((err: unknown) => console.error('Error sending chunk:', err));
        }
      };
    } catch {
      setError('Please allow microphone access.');
      cleanup();
    }
  }, [cleanup]);

  const stop = useCallback(() => {
    cleanup();
    setIsRecording(false);
  }, [cleanup]);

  return { isRecording, liveResult, error, start, stop };
}
