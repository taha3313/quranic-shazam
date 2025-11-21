import React from "react";
import IdentificationForm from "./components/IdentificationForm";

function App() {
  return (
    <div className="relative min-h-screen bg-gradient-to-br from-emerald-50 via-white to-emerald-100 
                    flex flex-col items-center py-12 px-4">
      {/* arabesque decorative overlay */}
      <div className="absolute inset-0 pointer-events-none pattern-fade"></div>
      <div className="relative z-10 w-full">
        <header className="relative z-10 text-center mb-8">
          <h1 className="text-5xl font-extrabold text-emerald-800 tracking-wide font-scheherazade">
            <span className="bg-white/50 px-2 rounded-md">القرآن Shazam</span>
          </h1>
          <p className="mt-2 text-gray-600 text-lg">
            <span className="bg-white/50 px-2 rounded-md">Identify the reciter using AI</span>
          </p>
        </header>

        <main className="w-full max-w-2xl px-4 mx-auto">
          <IdentificationForm />
        </main>
      </div>
    </div>
  );
}

export default App;
