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
    <div className="bg-white p-8 rounded-2xl card-glow shadow-soft-lg w-full">
      <form onSubmit={handleSubmit}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-3xl font-bold text-emerald-800 font-scheherazade">
            Identify Verse
          </h2>
          <span className="text-sm text-gray-400">Surah + Ayah from recitation</span>
        </div>

        <div className="mb-4">
          <label htmlFor="verse-audio-upload" className="block text-gray-700 text-sm font-medium mb-2">
            Upload Recitation Audio
          </label>
          <input
            id="verse-audio-upload"
            type="file"
            accept="audio/*"
            disabled={recording || loading}
            onChange={handleFileChange}
            className="w-full px-4 py-2 border rounded-lg bg-white
                       focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>

        <div className="mb-4 text-center text-gray-500">or</div>

        <div className="mb-6">
          <button
            type="button"
            onClick={handleRecordToggle}
            disabled={loading && !recording}
            className={`w-full px-4 py-3 font-semibold rounded-xl text-white
              ${recording ? 'bg-red-600' : 'bg-emerald-600'}`}
          >
            {recording ? 'Stop Listening' : 'Listen and Identify Verse'}
          </button>
        </div>

        <button
          type="submit"
          disabled={loading || recording || !file}
          className="w-full mt-2 bg-blue-700 text-white font-bold py-3 px-4 rounded-xl shadow-md disabled:opacity-60"
        >
          {loading ? 'Identifying verse…' : 'Identify Verse'}
        </button>
        <p className="mt-2 text-xs text-gray-400 text-center">
          Checks every 8 seconds and keeps listening while uncertain, up to one minute.
        </p>
      </form>

      {recording && (
        <p role="status" className="mt-4 text-amber-700">
          {result && !result.confident
            ? 'Several verses are still possible. Keep reciting; listening for more context…'
            : 'Listening to the recitation…'}
        </p>
      )}

      {audioURL && (
        <AudioPlayer
          src={audioURL}
          showJumpControls={false}
          customAdditionalControls={[]}
          className="mt-6"
        />
      )}

      {submitError && (
        <div className="mt-6 p-5 bg-red-50 border border-red-200 rounded-xl shadow-md text-red-700">
          <h3 className="text-lg font-semibold mb-2">Error</h3>
          <p>{submitError}</p>
        </div>
      )}

      {result && (
        <div className="mt-6 p-6 bg-white rounded-2xl card-glow shadow-md border border-emerald-100">
          <h3 className="text-2xl font-bold mb-3 text-emerald-800 font-scheherazade">
            Verse Result
          </h3>

          {!top && <p className="text-gray-600">No match found for this audio.</p>}
          {!result.confident && !recording && (
            <p className="mb-3 text-amber-700">
              {result.listen_limit_reached
                ? 'Still uncertain after one minute. Try a clearer recording with more surrounding verses.'
                : 'More context is needed. Record a longer continuous passage, including the following verse.'}
            </p>
          )}

          {top && (
            <div className="space-y-2">
              <p className="text-lg">
                <span className="font-semibold text-gray-600">Verse:</span>{' '}
                <span className="text-emerald-700 font-bold tracking-wide">
                  {verseLabel(top)}
                </span>
                {!result.confident && (
                  <span className="ml-2 text-sm text-amber-600">(low confidence)</span>
                )}
              </p>

              {top.text && (
                <p dir="rtl" className="text-2xl text-gray-800 font-scheherazade leading-loose">
                  {top.text}
                </p>
              )}

              <p className="text-md">
                <span className="font-semibold text-gray-600">Match score:</span>{' '}
                {`${(top.score * 100).toFixed(1)}%`}
                <span className="text-gray-400">
                  {' '}
                  ({top.words_matched}/{top.words_total} words matched)
                </span>
              </p>

              {result.matches.length > 1 && (
                <ul className="pt-2 text-sm text-gray-600 space-y-1">
                  {result.matches.slice(1).map((m) => (
                    <li key={`${m.surah}:${m.ayah_start}-${m.ayah_end}`}>
                      {verseLabel(m)} — {(m.score * 100).toFixed(1)}%
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}


### Rahman repeated-ayah suite

The real-audio suite checks four verified refrain positions (16, 30, 59,
77) across Alafasy, Husary and Minshawi. All 12 refrain-only cases request
more audio; all 12 refrain-plus-following-ayah cases correctly resolve their
specific ranges. The eight continued-listening regression tests also pass,
including ambiguity for all 31 canonical occurrences. Details and caveats:
backend/data/verse_audio_eval/RAHMAN_TEST.md and rahman_results.json.
Reproduce: cd backend && .venv/bin/python -m scripts.evaluate_rahman_audio.
