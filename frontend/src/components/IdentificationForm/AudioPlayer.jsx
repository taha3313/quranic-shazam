import React, { useRef, useState, useEffect } from "react";

const AudioPlayer = ({ src }) => {
  const audioRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);

  // play/pause toggle
  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    setIsPlaying(!isPlaying);
  };

  // update progress
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const updateProgress = () => {
      setProgress((audio.currentTime / audio.duration) * 100);
    };

    audio.addEventListener("timeupdate", updateProgress);
    audio.addEventListener("ended", () => setIsPlaying(false));

    return () => {
      audio.removeEventListener("timeupdate", updateProgress);
    };
  }, []);

  return (
    <div className="flex flex-col space-y-2 bg-emerald-50 p-4 rounded-xl shadow-md w-full">
      <audio ref={audioRef} src={src} hidden />
      <button
        onClick={togglePlay}
        className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-6 py-2 rounded-full w-full transition-colors"
      >
        {isPlaying ? "⏸ Pause" : "▶️ Play"}
      </button>

      <div className="h-2 bg-emerald-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-emerald-600 rounded-full transition-all duration-150"
          style={{ width: `${progress}%` }}
        ></div>
      </div>
    </div>
  );
};

export default AudioPlayer;
