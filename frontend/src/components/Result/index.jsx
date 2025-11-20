import React from "react";

const Result = ({ result, error }) => {
  if (error) {
    return (
      <div className="mt-6 p-5 bg-red-50 border border-red-200 rounded-xl shadow-md text-red-700">
        <h3 className="text-lg font-semibold mb-2">Error</h3>
        <p>{error}</p>
      </div>
    );
  }

  if (!result) return null;

  const top = result.matches?.[0];

  return (
    <div className="mt-6 p-6 bg-white rounded-2xl card-glow shadow-md border border-emerald-100">
      <h3 className="text-2xl font-bold mb-3 text-emerald-800 font-scheherazade">Identification Result</h3>

      <div className="space-y-2">
        <p className="text-lg">
          <span className="font-semibold text-gray-600">Reciter:</span>{" "}
          <span className="text-emerald-700 font-bold tracking-wide">{top?.reciter}</span>
        </p>

        <p className="text-md">
          <span className="font-semibold text-gray-600">Confidence:</span>{" "}
          <span>{top ? `${(top.score * 100).toFixed(2)}%` : "—"}</span>
        </p>
      </div>
    </div>
  );
};

export default Result;
