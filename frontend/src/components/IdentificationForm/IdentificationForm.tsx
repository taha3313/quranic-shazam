import { useEffect, useState } from 'react';
import type { ChangeEvent, FormEvent } from 'react';
import AudioPlayer from 'react-h5-audio-player';
import 'react-h5-audio-player/lib/styles.css';
import { identifyReciter } from '../../api';
import { useLiveReciter } from '../../hooks/useLiveReciter';
import type { IdentifyResponse } from '../../types';
import Result from '../Result';

export default function IdentificationForm() {
  const [file, setFile] = useState<File | null>(null);
  const [audioURL, setAudioURL] = useState<string | null>(null);
  const [result, setResult] = useState<IdentifyResponse | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const {
    isRecording,
    isChecking,
    recording,
    reset: resetRecording,
    liveResult,
    error: liveError,
    start: startRecording,
    stop: stopRecording,
  } = useLiveReciter();

  useEffect(() => {
    if (!recording) return;
    setFile(recording);
    setAudioURL(URL.createObjectURL(recording));
  }, [recording]);

  // Revoke object URLs on change/unmount to avoid leaks.
  useEffect(() => {
    return () => {
      if (audioURL) URL.revokeObjectURL(audioURL);
    };
  }, [audioURL]);

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0] ?? null;
    resetRecording();
    setFile(selected);
    setResult(null);
    setSubmitError(null);
    if (audioURL) URL.revokeObjectURL(audioURL);
    setAudioURL(selected ? URL.createObjectURL(selected) : null);
  };

  const handleRecordToggle = async () => {
    if (isRecording) {
      stopRecording();
      return;
    }
    setFile(null);
    setResult(null);
    setSubmitError(null);
    if (audioURL) {
      URL.revokeObjectURL(audioURL);
      setAudioURL(null);
    }
    await startRecording();
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setSubmitError('Please select a file first.');
      return;
    }
    setLoading(true);
    setResult(null);
    setSubmitError(null);
    try {
      const data = await identifyReciter(file);
      setResult(data);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Identification failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="studio-card">
      <form onSubmit={handleSubmit}>
        <div className="form-heading">
          <div>
            <h2>Identify a reciter</h2>
            <p>Upload a recording or let us listen with you.</p>
          </div>
          <span className="bismillah">بِسْمِ اللهِ الرَّحْمٰنِ الرَّحِيمِ</span>
        </div>

        <div className="mb-4">
          <label htmlFor="audio-upload" className="upload-label">Choose an audio recording</label>
          <input
            id="audio-upload"
            type="file"
            accept="audio/*"
            disabled={isRecording || isChecking || loading}
            onChange={handleFileChange}
            className="file-input"
          />
        </div>

        <div className="or-divider"><span>or listen now</span></div>

        <div className="mb-3">
          <button
            type="button"
            onClick={handleRecordToggle}
            disabled={loading || (isChecking && !isRecording)}
            className={`record-button${isRecording ? ' recording' : ''}`}
          >
            <span className="record-indicator" aria-hidden="true" />
            {isRecording ? 'Stop listening' : 'Start live listening'}
          </button>
        </div>

        <button
          type="submit"
          disabled={loading || isRecording || isChecking || !file}
          className="submit-button"
        >
          {loading || isChecking ? 'Listening for a match…' : 'Find this reciter'}
        </button>
        <p className="helper-copy">
          Live listening checks every few seconds and allows up to 30 seconds for a clear match.
        </p>
      </form>

      {isRecording && (
        <p role="status" aria-live="polite" className="live-status">
          <span className="record-indicator" aria-hidden="true" />
          {isChecking ? 'Listening to your recitation now…' : liveResult ? 'A few more seconds of recitation will help us be sure.' : 'Microphone is on. Recite a few seconds, then stop when ready.'}
        </p>
      )}
      {!isRecording && liveResult && !liveResult.confident && (
        <p role="status" className="live-status">
          We found a possible match. Try a clearer or longer passage for more confidence.
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

      {liveResult && !result && (
        <div className="mt-6">
          <Result result={liveResult} />
        </div>
      )}

      {result && <Result result={result} />}
      {(submitError ?? liveError) && <Result error={submitError ?? liveError} />}
    </div>
  );
}
