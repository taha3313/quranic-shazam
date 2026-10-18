import { useState } from 'react';
import type { KeyboardEvent } from 'react';
import IdentificationForm from './components/IdentificationForm';
import VerseForm from './components/VerseForm';

type Tab = 'reciter' | 'verse';

function App() {
  const [tab, setTab] = useState<Tab>('reciter');

  const handleModeKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next: Tab = event.key === 'Home' || event.key === 'ArrowLeft' ? 'reciter' : 'verse';
    setTab(next);
    document.getElementById(`${next}-tab`)?.focus();
  };

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" aria-hidden="true" />
      <div className="ambient ambient-two" aria-hidden="true" />
      <div className="pattern-layer" aria-hidden="true" />

      <header className="site-header">
        <a className="brand" href="#home" aria-label="Quranic Shazam home">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 48 48" fill="none">
              <path d="M30.8 8.2a16.5 16.5 0 1 0 9 25.7A14 14 0 0 1 30.8 8.2Z" fill="currentColor" />
              <path d="m34.8 9.1 1.1 3.3 3.4 1.1-3.4 1.1-1.1 3.4-1.1-3.4-3.4-1.1 3.4-1.1 1.1-3.3Z" fill="#C69A52" />
              <circle cx="15" cy="34" r="1.3" fill="#C69A52" />
            </svg>
          </span>
          <span className="brand-copy">
            <span className="brand-name">Quranic <b>Shazam</b></span>
            <span className="brand-kicker">A listening companion</span>
          </span>
        </a>
        <div className="header-note"><span className="status-dot" /> Made for the love of recitation</div>
      </header>

      <main id="home" className="main-layout">
        <section className="intro-panel" aria-labelledby="hero-title">
          <div className="intro-copy">
            <p className="eyebrow"><span /> RECOGNIZE THE RECITATION</p>
            <h1 id="hero-title">A voice can lead you <em>back to the verse.</em></h1>
            <p className="hero-description">
              Listen for the reciter you love, or find the ayah that stayed with you.
              A quiet little tool for a lifelong connection.
            </p>
            <div className="hero-qualities" aria-label="Available recognition modes">
              <span><i>01</i> Reciter recognition</span>
              <span><i>02</i> Verse discovery</span>
            </div>
          </div>

          <div className="hero-art" aria-hidden="true">
            <div className="arch-aura" />
            <svg className="mihrab-art" viewBox="0 0 340 420" fill="none">
              <defs>
                <linearGradient id="archFill" x1="35" y1="35" x2="300" y2="400" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#285b49" />
                  <stop offset="1" stopColor="#102f28" />
                </linearGradient>
                <linearGradient id="archLine" x1="36" y1="20" x2="305" y2="390" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#e5ca8e" />
                  <stop offset="1" stopColor="#a77d3f" />
                </linearGradient>
              </defs>
              <path d="M19 403V180C19 117 74 68 170 13c96 55 151 104 151 167v223H19Z" fill="url(#archFill)" stroke="url(#archLine)" strokeWidth="2" />
              <path d="M44 403V184c0-51 44-91 126-139 82 48 126 88 126 139v219H44Z" stroke="#d4b875" strokeOpacity=".45" />
              <path d="M65 403V188c0-43 37-77 105-117 68 40 105 74 105 117v215" stroke="#d4b875" strokeOpacity=".2" />
              <path d="M170 74 184 116 226 102 202 139 239 163 195 163 195 207 170 171 145 207 145 163 101 163 138 139 114 102 156 116 170 74Z" stroke="#d8bb77" strokeOpacity=".56" strokeWidth="1.4" />
              <circle cx="170" cy="153" r="45" stroke="#d8bb77" strokeOpacity=".48" />
              <circle cx="170" cy="153" r="35" stroke="#d8bb77" strokeOpacity=".32" strokeDasharray="2 5" />
              <path d="M164 139v30m0-30c-6-4-12-5-18-2v27c6-3 12-2 18 2m0-27c6-4 12-5 18-2v27c-6-3-12-2-18 2" stroke="#f1e5c3" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M74 248h192M74 258h192" stroke="#d8bb77" strokeOpacity=".25" />
              <path d="m170 279 8 21 22-8-13 19 19 13-22 0 0 22-14-18-14 18v-22h-22l19-13-13-19 22 8 8-21Z" stroke="#d8bb77" strokeOpacity=".48" />
              <circle cx="68" cy="111" r="2" fill="#e4cc94"/><circle cx="272" cy="111" r="2" fill="#e4cc94"/>
              <path d="M65 346h210" stroke="#d8bb77" strokeOpacity=".35" />
              <text x="170" y="373" fill="#e9d9ad" fontSize="8" letterSpacing="3" textAnchor="middle">LISTEN · REFLECT · RECOGNIZE</text>
            </svg>
            <span className="art-star star-a">✦</span><span className="art-star star-b">✧</span>
          </div>
        </section>

        <section className="recognition-section" aria-label="Audio recognition">
          <div className="mode-switch" role="tablist" aria-label="Choose what to recognize">
            <button
              id="reciter-tab"
              type="button"
              role="tab"
              aria-selected={tab === 'reciter'}
              aria-controls="recognition-panel"
              onClick={() => setTab('reciter')}
              onKeyDown={handleModeKeyDown}
              className={tab === 'reciter' ? 'mode-tab active' : 'mode-tab'}
            >
              <span className="mode-icon" aria-hidden="true">◖</span>
              <span><b>Find a reciter</b><small>Recognize a familiar voice</small></span>
              <span className="tab-arrow" aria-hidden="true">↗</span>
            </button>
            <button
              id="verse-tab"
              type="button"
              role="tab"
              aria-selected={tab === 'verse'}
              aria-controls="recognition-panel"
              onClick={() => setTab('verse')}
              onKeyDown={handleModeKeyDown}
              className={tab === 'verse' ? 'mode-tab active' : 'mode-tab'}
            >
              <span className="mode-icon verse-icon" aria-hidden="true">۞</span>
              <span><b>Find a verse</b><small>Discover the ayah being read</small></span>
              <span className="tab-arrow" aria-hidden="true">↗</span>
            </button>
          </div>
          <div id="recognition-panel" role="tabpanel" aria-labelledby={tab === 'reciter' ? 'reciter-tab' : 'verse-tab'} key={tab} className="panel-enter">
            {tab === 'reciter' ? <IdentificationForm /> : <VerseForm />}
          </div>
          <p className="privacy-note"><span aria-hidden="true">✧</span> Your recordings are only used to find a match.</p>
        </section>
      </main>

      <footer className="site-footer">
        <span className="footer-ornament" aria-hidden="true">✦ ─────── ✦</span>
        <p dir="rtl" lang="ar">وَرَتِّلِ الْقُرْآنَ تَرْتِيلًا</p>
        <span>“And recite the Qur’an with measured recitation.” <small>— Al-Muzzammil 73:4</small></span>
      </footer>
    </div>
  );
}

export default App;
