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
            <div className="art-orbit orbit-outer" />
            <div className="art-orbit orbit-inner" />
            <div className="art-medallion">
              <svg viewBox="0 0 220 220" fill="none">
                <circle cx="110" cy="110" r="75" stroke="currentColor" strokeOpacity=".22" />
                <circle cx="110" cy="110" r="61" stroke="currentColor" strokeOpacity=".3" strokeDasharray="2 6" />
                <path d="M110 48 121 88l39-18-18 39 40 11-40 11 18 39-39-18-11 40-11-40-39 18 18-39-40-11 40-11-18-39 39 18 11-40Z" fill="currentColor" fillOpacity=".08" stroke="currentColor" strokeOpacity=".48" />
                <circle cx="110" cy="110" r="29" fill="#F8F5EB" stroke="currentColor" strokeOpacity=".4" />
                <path d="M108 91v37m0-37c-7-5-15-6-23-3v34c8-3 16-2 23 3m0-34c7-5 15-6 23-3v34c-8-3-16-2-23 3" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <div className="sound-wave"><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /></div>
            <span className="art-caption">LISTEN · REFLECT · RECOGNIZE</span>
            <span className="art-star star-a">✳</span><span className="art-star star-b">✦</span>
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
