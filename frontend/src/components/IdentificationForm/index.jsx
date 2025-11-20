import React, { useState, useEffect } from "react";
import Result from "../Result";
import AudioPlayer from "react-h5-audio-player";
import "react-h5-audio-player/lib/styles.css";

const IdentificationForm = () => {
  const [file, setFile] = useState(null);
  const [audioURL, setAudioURL] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState(null);
  const [audioBlob, setAudioBlob] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  // Clean up object URL on unmount or when audioURL changes
  useEffect(() => {
    return () => {
      if (audioURL) {
        URL.revokeObjectURL(audioURL);
      }
    };
  }, [audioURL]);

  const handleFileChange = (event) => {
    const selected = event.target.files[0];
    setFile(selected);
    setAudioBlob(null);

    if (selected) {
      const url = URL.createObjectURL(selected);
      setAudioURL(url);
    }
  };

  const handleRecord = async () => {
    if (isRecording) {
      mediaRecorder.stop();
      setIsRecording(false);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const recorder = new MediaRecorder(stream);
        setMediaRecorder(recorder);
        recorder.start();
        setIsRecording(true);

        setFile(null);
        setAudioURL(null);

        const chunks = [];
        recorder.ondataavailable = (event) => {
          chunks.push(event.data);
        };

        recorder.onstop = () => {
          const blob = new Blob(chunks, { type: "audio/wav" });
          setAudioBlob(blob);

          const url = URL.createObjectURL(blob);
          setAudioURL(url);
        };
      } catch (err) {
        setError(
          "Microphone access was denied. Please allow microphone access to record audio."
        );
      }
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
    if (file) {
      formData.append("file", file);
    } else if (audioBlob) {
      formData.append("file", audioBlob, "recording.wav");
    }

    try {
      const response = await fetch("http://127.0.0.1:8000/identify_reciter", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => null);
        throw new Error(err?.detail || "The identification has failed");
      }

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
          <label
            htmlFor="file"
            className="block text-gray-700 text-sm font-medium mb-2"
          >
            Upload Audio File
          </label>
          <input
            type="file"
            id="file"
            accept="audio/*"
            onChange={handleFileChange}
            className="w-full px-4 py-2 border rounded-lg text-gray-700 bg-white input-file
                       focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
          />
        </div>

        <div className="mb-4 text-center text-gray-500">or</div>

        <div className="mb-6">
          <button
            type="button"
            onClick={handleRecord}
            className={`w-full px-4 py-3 font-semibold rounded-xl text-white transition-shadow shadow-md
              ${isRecording ? "bg-red-600 hover:bg-red-700" : "bg-emerald-600 hover:bg-emerald-700"}`}
          >
            {isRecording ? "Stop Recording" : "Record Audio"}
          </button>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full mt-2 bg-blue-700 hover:bg-blue-800 text-white font-bold py-3 px-4 rounded-xl shadow-md disabled:opacity-60"
        >
          {loading ? "Identifying..." : "Identify"}
        </button>
      </form>

      {/* 🔥 Use react-h5-audio-player here */}
{audioURL && (
  <div className="mt-6 relative">
    {/* Optional: small arabesque overlay */}
    <div className="absolute inset-0 pointer-events-none bg-arabesque-pattern opacity-5 rounded-xl"></div>
    
    <AudioPlayer
      src={audioURL}
      onPlay={(e) => console.log("Playing audio")}
      showJumpControls={false}
      customAdditionalControls={[]}
      className="rhap-theme-quranic relative z-10"
    />
  </div>
)}


      {result && <Result result={result} />}
      {error && <Result error={error} />}
    </div>
  );
};

export default IdentificationForm;
