import Link from "next/link";

import { Logo } from "@/Logo";

// Marketing landing page. Static — no auth, no API calls. "Open the app" routes
// into the functional web client under /login.
export default function Landing() {
  return (
    <>
      <nav className="nav">
        <div className="container nav-inner">
          <Logo />
          <div className="nav-links">
            <a href="#features" className="hide-sm">
              Features
            </a>
            <a href="#how" className="hide-sm">
              How it works
            </a>
            <Link href="/login">Open the app →</Link>
          </div>
        </div>
      </nav>

      <header className="hero">
        <div className="container hero-grid">
          <div>
            <Logo hero iconSize={36} />
            <h1>
              Tell it once.
              <br />
              <span className="amber">Ask it anytime.</span>
            </h1>
            <p className="lead">
              Save the random stuff you&apos;d forget — plates, passwords,
              birthdays, Wi‑Fi — then just ask for it later like texting a
              friend who never blanks.
            </p>
            <div className="hero-cta">
              <Link href="/login" className="btn btn-primary">
                Open the app →
              </Link>
              <a href="#how" className="btn btn-ghost">
                See how it works
              </a>
            </div>
            <p className="hero-note">
              No setup. Sign in and start remembering in seconds.
            </p>
          </div>

          <div className="demo">
            <div className="demo-head">
              <span className="title">CONVERSATION</span>
            </div>
            <div className="bubbles">
              <div className="bubble user">My car license plate is 8XYZ123</div>
              <div className="bubble bot">
                <span className="tag">Stored</span>
                Got it — I&apos;ll remember your license plate is 8XYZ123.
              </div>
              <div className="bubble user">What&apos;s my license plate?</div>
              <div className="bubble bot">
                <span className="tag">Recalled</span>
                Your car license plate is <b>8XYZ123</b>.
              </div>
            </div>
          </div>
        </div>
      </header>

      <section className="block" id="features">
        <div className="container">
          <span className="section-kicker">Why MyMemory</span>
          <h2 className="section-title">
            A second memory that actually remembers.
          </h2>
          <p className="section-sub">
            No folders, no tags, no forms. Just talk to it like a person and it
            keeps your facts straight.
          </p>
          <div className="features">
            <div className="card">
              <div className="ico">Say it</div>
              <h3>Just talk</h3>
              <p>
                Type or speak naturally. MyMemory figures out whether you&apos;re
                telling it something new or asking for it back.
              </p>
            </div>
            <div className="card">
              <div className="ico">Recall</div>
              <h3>Semantic search</h3>
              <p>
                Ask in your own words. Vector search finds the right memory even
                when you don&apos;t use the exact phrasing you saved.
              </p>
            </div>
            <div className="card">
              <div className="ico">Private</div>
              <h3>Yours alone</h3>
              <p>
                Every memory is scoped to your account. Answers are grounded only
                in what you&apos;ve saved — and cite their source.
              </p>
            </div>
            <div className="card">
              <div className="ico">Voice</div>
              <h3>Hands-free</h3>
              <p>
                On the iOS app, speak with on-device transcription. The web app
                keeps the same fast chat experience.
              </p>
            </div>
            <div className="card">
              <div className="ico">Browse</div>
              <h3>See everything</h3>
              <p>
                Every fact you save shows up in a clean list. Review what
                MyMemory knows and delete anything with one tap.
              </p>
            </div>
            <div className="card">
              <div className="ico">Grounded</div>
              <h3>Cited answers</h3>
              <p>
                Replies are drawn from your memories via retrieval-augmented
                generation — not invented.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="block" id="how">
        <div className="container">
          <span className="section-kicker">How it works</span>
          <h2 className="section-title">Three steps. That&apos;s the whole thing.</h2>
          <div className="steps">
            <div className="step">
              <div className="num">1</div>
              <h3>Tell it a fact</h3>
              <p>
                &ldquo;My passport expires in March 2029.&rdquo; MyMemory
                normalizes it, embeds it, and saves it privately.
              </p>
            </div>
            <div className="step">
              <div className="num">2</div>
              <h3>Forget about it</h3>
              <p>
                Go live your life. Your memories sit safely in your own store,
                ready whenever you need them.
              </p>
            </div>
            <div className="step">
              <div className="num">3</div>
              <h3>Ask it back</h3>
              <p>
                &ldquo;When does my passport expire?&rdquo; It retrieves the
                closest memories and answers — with sources.
              </p>
            </div>
          </div>
        </div>
      </section>

      <div className="container">
        <div className="cta">
          <h2>Start remembering everything.</h2>
          <p>
            Open the web app and tell MyMemory your first fact. It only gets more
            useful the more you trust it with.
          </p>
          <Link href="/login" className="btn btn-primary">
            Open the app →
          </Link>
        </div>
      </div>

      <footer>
        <div className="container footer">
          <span>© {2026} MyMemory — your private memory store.</span>
          <span>Built with FastAPI · pgvector · Claude on Bedrock</span>
        </div>
      </footer>
    </>
  );
}
