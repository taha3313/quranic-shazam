import type { IdentifyResponse } from '../../types';

interface ResultProps {
  result?: IdentifyResponse | null;
  error?: string | null;
}

export default function Result({ result, error }: ResultProps) {
  if (error) {
    return (
      <div className="mt-6 p-5 bg-red-50 border border-red-200 rounded-xl shadow-md text-red-700">
        <h3 className="text-lg font-semibold mb-2">Error</h3>
        <p>{error}</p>
      </div>
    );
  }

  if (!result || result.matches.length === 0) return null;

  const top = result.matches[0];

  return (
    <div className="mt-6 p-6 bg-white rounded-2xl card-glow shadow-md border border-emerald-100">
      <h3 className="text-2xl font-bold mb-3 text-emerald-800 font-scheherazade">
        Identification Result
      </h3>

      <div className="space-y-2">
        <p className="text-lg">
          <span className="font-semibold text-gray-600">Reciter:</span>{' '}
          <span className="text-emerald-700 font-bold tracking-wide">{top.display ?? top.reciter}</span>
        </p>

        <p className="text-md">
          <span className="font-semibold text-gray-600">Confidence:</span>{' '}
          <span>{`${(top.score * 100).toFixed(2)}%`}</span>
        </p>

        {result.matches.length > 1 && (
          <ul className="pt-2 text-sm text-gray-600 space-y-1">
            {result.matches.slice(1).map((m) => (
              <li key={m.reciter}>
                {m.display ?? m.reciter} — {(m.score * 100).toFixed(2)}%
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
