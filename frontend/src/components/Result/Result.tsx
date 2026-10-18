import type { IdentifyResponse } from '../../types';

interface ResultProps {
  result?: IdentifyResponse | null;
  error?: string | null;
}

export default function Result({ result, error }: ResultProps) {
  if (error) {
    return <div role="alert" className="error-card"><b>We couldn’t complete the match</b>{error}</div>;
  }

  if (!result || result.matches.length === 0) return null;

  const top = result.matches[0];
  const score = Math.max(0, Math.min(100, top.score * 100));

  return (
    <section className="result-card" aria-live="polite" aria-label="Reciter match">
      <div className="result-topline">
        <h3 className="result-title">A voice we recognize</h3>
        <span className={`result-badge${result.confident ? '' : ' uncertain'}`}>
          {result.confident ? 'CLEAR MATCH' : 'POSSIBLE MATCH'}
        </span>
      </div>
      <div className="primary-match">
        <span className="match-seal" aria-hidden="true">✧</span>
        <div className="match-info">
          <span className="match-caption">Closest reciter</span>
          <span className="match-name">{top.display ?? top.reciter}</span>
          <div className="score-track" role="meter" aria-label="Match similarity" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(score)} aria-valuetext={`${score.toFixed(1)} percent`}>
            <div className="score-fill" style={{ width: `${score}%` }} />
          </div>
        </div>
        <span className="match-score">{score.toFixed(1)}%</span>
      </div>
      {result.matches.length > 1 && (
        <ul className="candidate-list" aria-label="Other possible reciters">
          {result.matches.slice(1).map((match) => (
            <li key={match.reciter}>
              <span>{match.display ?? match.reciter}</span>
              <b>{(match.score * 100).toFixed(1)}%</b>
            </li>
          ))}
        </ul>
      )}
      {!result.confident && (
        <p className="result-warning">A longer, clearer passage can help distinguish between similar voices.</p>
      )}
    </section>
  );
}
