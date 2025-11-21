import React, { useState, useEffect, useRef } from "react";
import Result from "../Result";
import AudioPlayer from "react-h5-audio-player";
import "react-h5-audio-player/lib/styles.css";

const IdentificationForm = () => {
  const [file, setFile] = useState(null);
  const [audioURL, setAudioURL] = useState(null);
  const [audioBlob, setAudioBlob] = useState(null);
  const [isRecording, setIsRecording] = useState(false);

  const [result, setResult] = useState(null);
  const [liveResult, setLiveResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const mediaRecorderRef = useRef(null);
  const isRecordingRef = useRef(false);
  const wsRef = useRef(null);

  useEffect(() => {
    return () => {
      if (audioURL) URL.revokeObjectURL(audioURL);
      if (wsRef.current) wsRef.current.close();
    };
  }, [audioURL]);

  const handleFileChange = (event) => {
    const selected = event.target.files[0];
    setFile(selected);
    setAudioBlob(null);
    setLiveResult(null);

    if (selected) {
      setAudioURL(URL.createObjectURL(selected));
    }
  };

  const handleRecord = async () => {
    if (isRecording) {
      isRecordingRef.current = false;
      mediaRecorderRef.current?.stop();
      wsRef.current?.close();
      wsRef.current = null;

      setIsRecording(false);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      const ws = new WebSocket("ws://127.0.0.1:8000/live_reciter");
      wsRef.current = ws;

      ws.onopen = () => console.log("WebSocket connected.");
      ws.onerror = (e) => console.error("WebSocket error:", e);
      ws.onclose = () => console.log("WebSocket closed.");
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setLiveResult(data);
      };

      const recorder = new MediaRecorder(stream, {
        mimeType: "audio/webm;codecs=opus",
      });
      mediaRecorderRef.current = recorder;

      isRecordingRef.current = true;
      setIsRecording(true);

      setFile(null);
      setAudioBlob(null);
      setAudioURL(null);
      setLiveResult(null);

      recorder.start(300); // smaller chunks fix FFmpeg parsing

      recorder.ondataavailable = async (event) => {
        if (!isRecordingRef.current) return;

        if (event.data && event.data.size > 0 && ws.readyState === WebSocket.OPEN) {
          try {
            // Wrap chunk into a valid blob to preserve WebM headers
            const blob = new Blob([event.data], { type: "audio/webm;codecs=opus" });
            const arrayBuf = await blob.arrayBuffer();
            ws.send(arrayBuf);
          } catch (err) {
            console.error("Error sending chunk:", err);
          }
        }
      };

      recorder.onstop = () => {
        isRecordingRef.current = false;
        setAudioBlob(new Blob([], { type: "audio/wav" }));
      };
    } catch (err) {
      console.log("Mic error:", err);
      setError("Please allow microphone access.");
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!file && !audioBlob) {
      setError("Please select a file or record audio first.");
      return;
    }

    setLoading(true);
    setResult(null);
    setError(null);

    const formData = new FormData();
    if (file) formData.append("file", file);
    else formData.append("file", audioBlob, "recording.wav");

    try {
      const response = await fetch("http://127.0.0.1:8000/identify_reciter", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Identification failed");

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
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
          <label className="block text-gray-700 text-sm font-medium mb-2">
            Upload Audio File
          </label>
          <input
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
            onClick={handleRecord}
            className={`w-full px-4 py-3 font-semibold rounded-xl text-white
              ${isRecording ? "bg-red-600" : "bg-emerald-600"}`}
          >
            {isRecording ? "Stop Recording (Live Mode)" : "Record Live Audio"}
          </button>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full mt-2 bg-blue-700 text-white font-bold py-3 px-4 rounded-xl shadow-md disabled:opacity-60"
        >
          {loading ? "Identifying..." : "Identify Uploaded Audio"}
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
      {error && <Result error={error} />}
    </div>
  );
};

export default IdentificationForm;