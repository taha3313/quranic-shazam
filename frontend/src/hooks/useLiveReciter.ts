import { useCallback, useEffect, useRef, useState } from 'react';
import { identifyReciter } from '../api';
import type { IdentifyResponse } from '../types';

/** Check complete, accumulated recordings, just like live verse recognition. */
export function useLiveReciter() {
  const [isRecording, setIsRecording] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [liveResult, setLiveResult] = useState<IdentifyResponse | null>(null);
  const [recording, setRecording] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const sessionRef = useRef(0);
  const activeRef = useRef(false);
  const deadlineRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cleanup = useCallback(() => {
    if (deadlineRef.current) clearTimeout(deadlineRef.current);
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') recorder.stop();
    recorder?.stream.getTracks().forEach((track) => track.stop());
    recorderRef.current = null;
    activeRef.current = false;
  }, []);

  useEffect(() => () => {
    sessionRef.current += 1;
    cleanup();
  }, [cleanup]);

  const reset = useCallback(() => {
    sessionRef.current += 1;
    cleanup();
    setIsRecording(false);
    setIsChecking(false);
    setLiveResult(null);
    setRecording(null);
    setError(null);
  }, [cleanup]);

  const start = useCallback(async () => {
    if (activeRef.current) return;
    reset();
    activeRef.current = true;
    const session = sessionRef.current;
    let stream: MediaStream | null = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (session !== sessionRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;
      const chunks: Blob[] = [];
      let checking = false;
      let resolved = false;
      let pending: Blob | null = null;
      const snapshot = () => new Blob(chunks, { type: recorder.mimeType });
      const checkAudio = async (blob: Blob) => {
        pending = blob;
        if (checking || resolved) return;
        checking = true;
        setIsChecking(true);
        try {
          while (pending && !resolved && session === sessionRef.current) {
            const next = pending;
            pending = null;
            const data = await identifyReciter(next, 'recitation.webm');
            if (session !== sessionRef.current) return;
            setLiveResult(data);
            if (data.confident) {
              resolved = true;
              pending = null;
              if (recorder.state !== 'inactive') recorder.stop();
            }
          }
        } catch (err) {
          if (session === sessionRef.current) {
            resolved = true;
            setError(err instanceof Error ? err.message : 'Reciter identification failed.');
            if (recorder.state !== 'inactive') recorder.stop();
          }
        } finally {
          checking = false;
          if (session === sessionRef.current) setIsChecking(false);
        }
      };
      recorder.ondataavailable = (event) => {
        if (session !== sessionRef.current || !event.data.size) return;
        chunks.push(event.data);
        if (!resolved) void checkAudio(snapshot());
      };
      recorder.onstop = () => {
        recorder.stream.getTracks().forEach((track) => track.stop());
        if (session !== sessionRef.current) return;
        if (deadlineRef.current) clearTimeout(deadlineRef.current);
        activeRef.current = false;
        setIsRecording(false);
        const blob = snapshot();
        if (blob.size) {
          setRecording(new File([blob], 'recitation.webm', { type: blob.type }));
        } else {
          setError('Recording was too short. Please record a few seconds of recitation.');
        }
      };
      recorder.start(8000);
      setIsRecording(true);
      deadlineRef.current = setTimeout(() => {
        if (recorder.state !== 'inactive') recorder.stop();
      }, 30000);
    } catch (err) {
      stream?.getTracks().forEach((track) => track.stop());
      if (session !== sessionRef.current) return;
      cleanup();
      setIsRecording(false);
      setError(err instanceof Error ? err.message : 'Could not start live recording.');
    }
  }, [cleanup, reset]);

  const stop = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') recorder.stop();
  }, []);

  return { isRecording, isChecking, liveResult, recording, error, start, stop, reset };
}
