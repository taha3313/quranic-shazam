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
    liveResult,
    error: liveError,
    start: startRecording,
    stop: stopRecording,
  } = useLiveReciter();

  // Revoke object URLs on change/unmount to avoid leaks.
  useEffect(() => {
    return () => {
      if (audioURL) URL.revokeObjectURL(audioURL);
    };
  }, [audioURL]);

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0] ?? null;
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
    <div className="bg-white p-8 rounded-2xl card-glow shadow-soft-lg w-full">
      <form onSubmit={handleSubmit}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-3xl font-bold text-emerald-800 font-scheherazade">
            Identify Reciter
          </h2>
          <span className="bismillah">بِسْمِ اللهِ الرَّحْمٰنِ الرَّحِيمِ</span>
        </div>

        <div className="mb-4">
          <label htmlFor="audio-upload" className="block text-gray-700 text-sm font-medium mb-2">
            Upload Audio File
          </label>
          <input
            id="audio-upload"
            type="file"
            accept="audio/*"
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
            className={`w-full px-4 py-3 font-semibold rounded-xl text-white
              ${isRecording ? 'bg-red-600' : 'bg-emerald-600'}`}
          >
            {isRecording ? 'Stop Recording (Live Mode)' : 'Record Live Audio'}
          </button>
        </div>

        <button
          type="submit"
          disabled={loading || !file}
          className="w-full mt-2 bg-blue-700 text-white font-bold py-3 px-4 rounded-xl shadow-md disabled:opacity-60"
        >
          {loading ? 'Identifying...' : 'Identify Uploaded Audio'}
        </button>
      </form>

      {audioURL && (
        <AudioPlayer
          src={audioURL}
          showJumpControls={false}
          customAdditionalControls={[]}
          className="mt-6"
        />
      )}

      {liveResult && (
        <div className="mt-6">
          <Result result={liveResult} />
        </div>
      )}

      {result && <Result result={result} />}
      {(submitError ?? liveError) && <Result error={submitError ?? liveError} />}
    </div>
  );
}
