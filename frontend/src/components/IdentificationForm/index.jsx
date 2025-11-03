import React, { useState } from "react";
import "./style.css";

const IdentificationForm = () => {
  const [file, setFile] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState(null);
  const [audioBlob, setAudioBlob] = useState(null);

  const handleFileChange = (event) => {
    setFile(event.target.files[0]);
  };

  const handleRecord = async () => {
    if (isRecording) {
      mediaRecorder.stop();
      setIsRecording(false);
    } else {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      const recorder = new MediaRecorder(stream);
      setMediaRecorder(recorder);
      recorder.start();
      setIsRecording(true);

      recorder.ondataavailable = (event) => {
        setAudioBlob(event.data);
      };
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const formData = new FormData();
    if (file) {
      formData.append("file", file);
    } else if (audioBlob) {
      formData.append("file", audioBlob, "recording.wav");
    }

    try {
      const response = await fetch("http://localhost:8000/reciter/identify", {
        method: "POST",
        body: formData,
      });
      const data = await response.json();
      alert(`Reciter is: ${data.reciter}`);
    } catch (error) {
      console.error("Error identifying reciter:", error);
      alert("Error identifying reciter");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="identification-form">
      <h2>Identify Reciter</h2>
      <div className="form-group">
        <label htmlFor="file">Upload audio file</label>
        <input
          type="file"
          id="file"
          accept="audio/*"
          onChange={handleFileChange}
        />
      </div>
      <div className="form-group">
        <button type="button" onClick={handleRecord}>
          {isRecording ? "Stop Recording" : "Record Audio"}
        </button>
      </div>
      <button type="submit">Identify</button>
    </form>
  );
};

export default IdentificationForm;