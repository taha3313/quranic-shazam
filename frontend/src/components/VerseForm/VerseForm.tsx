import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent, FormEvent } from 'react';
import AudioPlayer from 'react-h5-audio-player';
import 'react-h5-audio-player/lib/styles.css';
import { identifyVerse } from '../../api';
import type { IdentifyVerseResponse, VerseMatch } from '../../types';

function verseLabel(m: VerseMatch): string {
  const name = m.surah_name ?? `Surah ${m.surah}`;
  const ref =
    m.ayah_start === m.ayah_end
      ? `${m.surah}:${m.ayah_start}`
      : `${m.surah}:${m.ayah_start}-${m.ayah_end}`;
  return `${name} (${ref})`;
}

export default function VerseForm() {
  const [file, setFile] = useState<File | null>(null);
  const [audioURL, setAudioURL] = useState<string | null>(null);
  const [result, setResult] = useState<IdentifyVerseResponse | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const deadlineRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sessionRef = useRef(0);

  useEffect(() => {
    return () => {
      if (audioURL) URL.revokeObjectURL(audioURL);
    };
  }, [audioURL]);

  useEffect(() => () => {
    sessionRef.current += 1;
    if (deadlineRef.current) clearTimeout(deadlineRef.current);
    const recorder = mediaRecorderRef.current;
    if (recorder?.state === 'recording') recorder.stop();
    recorder?.stream.getTracks().forEach((t) => t.stop());
  }, []);

  const applyAudio = (f: File | null, url: string | null) => {
    sessionRef.current += 1;
    setResult(null);
    setSubmitError(null);
    setFile(f);
    setAudioURL(url);
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0] ?? null;
    applyAudio(selected, selected ? URL.createObjectURL(selected) : null);
  };

  const handleRecordToggle = async () => {
    if (recording) {
      mediaRecorderRef.current?.stop();
      return;
    }
    const session = ++sessionRef.current;
    setResult(null);
    setSubmitError(null);
    setFile(null);
    setAudioURL(null);
    let requestedStream: MediaStream | null = null;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      requestedStream = stream;
      if (session !== sessionRef.current) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      let checking = false;
      let resolved = false;
      let pending: Blob | null = null;

      const checkAudio = async (blob: Blob) => {
        pending = blob;
        if (checking || resolved) return;
        checking = true;
        setLoading(true);
        try {
          while (pending && !resolved && session === sessionRef.current) {
            const next = pending;
            pending = null;
            const data = await identifyVerse(next, 'recitation.webm', 3, true, true);
            if (session !== sessionRef.current) return;
            setResult(data);
            if (data.confident || data.listen_limit_reached) {
              resolved = true;
              pending = null;
              if (recorder.state === 'recording') recorder.stop();
            }
          }
        } catch (err) {
          if (session === sessionRef.current) {
            resolved = true;
            setSubmitError(err instanceof Error ? err.message : 'Verse identification failed');
            if (recorder.state === 'recording') recorder.stop();
          }
        } finally {
          checking = false;
          if (session === sessionRef.current) setLoading(false);
        }
      };

      recorder.ondataavailable = (e) => {
        if (session !== sessionRef.current || !e.data.size) return;
        chunksRef.current.push(e.data);
        if (!resolved) {
          void checkAudio(new Blob(chunksRef.current, { type: recorder.mimeType }));
        }
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        if (deadlineRef.current) clearTimeout(deadlineRef.current);
        if (session !== sessionRef.current) return;
        setRecording(false);
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || 'audio/webm',
        });
        setFile(new File([blob], 'recitation.webm', { type: blob.type }));
        setAudioURL(URL.createObjectURL(blob));
      };
      mediaRecorderRef.current = recorder;
      recorder.start(8000);
      deadlineRef.current = setTimeout(() => {
        if (recorder.state === 'recording') recorder.stop();
      }, 60000);
      setRecording(true);
    } catch {
      requestedStream?.getTracks().forEach((t) => t.stop());
      setRecording(false);
      setSubmitError('Could not access the microphone.');
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setSubmitError('Please select or record a recitation first.');
      return;
    }
    setLoading(true);
    setResult(null);
    setSubmitError(null);
    try {
      const data = await identifyVerse(file, file.name, 3, true, true);
      setResult(data);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Verse identification failed');
    } finally {
      setLoading(false);
    }
  };

  const top = result?.matches[0];

  return (
    <div className="studio-card">
      <form onSubmit={handleSubmit} aria-busy={loading && !recording}>
        <div className="form-heading">
          <div>
            <h2><span className="form-heading-mark" aria-hidden="true">۞</span>Find a verse</h2>
            <p>We listen for the words and surrounding context.</p>
          </div>
          <span className="bismillah">بِسْمِ اللهِ الرَّحْمٰنِ الرَّحِيمِ</span>
        </div>

        <div className="mb-4">
          <label htmlFor="verse-audio-upload" className="upload-label">Choose an audio recording</label>
          <input
            id="verse-audio-upload"
            type="file"
            accept="audio/*"
            aria-describedby="verse-audio-help"
            disabled={recording || loading}
            onChange={handleFileChange}
            className="file-input"
          />
        </div>

        <div className="or-divider"><span>or recite now</span></div>

        <div className="mb-3">
          <button
            type="button"
            onClick={handleRecordToggle}
            disabled={loading && !recording}
            className={`record-button${recording ? ' recording' : ''}`}
          >
            <span className="record-indicator" aria-hidden="true" />
            {recording ? 'Stop listening' : 'Start live listening'}
          </button>
        </div>

        <button
          type="submit"
          disabled={loading || recording || !file}
          className="submit-button"
        >
          {loading ? 'Listening for the ayah…' : 'Find this verse'}
        </button>
        <p id="verse-audio-help" className="helper-copy">
          More surrounding recitation helps us find the right ayah, especially with repeated verses.
        </p>
      </form>

      {!recording && loading && (
        <p role="status" aria-live="polite" aria-atomic="true" className="sr-only">Searching the recitation for a verse.</p>
      )}

      {recording && (
        <p role="status" aria-live="polite" className="live-status">
          <span className="record-indicator" aria-hidden="true" />
          {result && !result.confident
            ? 'A few verses are still possible. Keep reciting so we can hear more context.'
            : 'Microphone is on. Recite a continuous passage, then stop when ready.'}
        </p>
      )}

      {audioURL && (
        <div className="audio-player-wrap">
          <AudioPlayer
            src={audioURL}
            showJumpControls={false}
            customAdditionalControls={[]}
          />
        </div>
      )}

      {submitError && (
        <div role="alert" className="error-card"><b>We couldn’t complete the match</b>{submitError}</div>
      )}

      {result && (
        <section className="result-card" aria-live="polite" aria-label="Verse match">
          <div className="result-topline">
            <h3 className="result-title">A verse from the recitation</h3>
            {top && <span className={`result-badge${result.confident ? '' : ' uncertain'}`}>{result.confident ? 'CLEAR MATCH' : 'LISTENING FOR CONTEXT'}</span>}
          </div>

          {!top && <p className="text-gray-600">No match found for this audio.</p>}
          {!result.confident && !recording && (
            <p className="result-warning">
              {result.listen_limit_reached
                ? 'Still uncertain after one minute. Try a clearer recording with more surrounding verses.'
                : 'More context is needed. Record a longer continuous passage, including the following verse.'}
            </p>
          )}

          {top && (
            <div>
              <p className="match-caption">Closest passage</p>
              <p className="match-name">{verseLabel(top)}</p>

              {top.text && (
                <p dir="rtl" lang="ar" className="arabic-verse">
                  {top.text}
                </p>
              )}

              <p className="verse-meta">
                Similarity{' '}
                {`${(top.score * 100).toFixed(1)}%`}
                <span>
                  {' · '}
                  ({top.words_matched}/{top.words_total} words matched)
                </span>
              </p>

              {result.matches.length > 1 && (
                <ul className="candidate-list">
                  {result.matches.slice(1).map((m) => (
                    <li key={`${m.surah}:${m.ayah_start}-${m.ayah_end}`}>
                      <span>{verseLabel(m)}</span><b>{(m.score * 100).toFixed(1)}%</b>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
