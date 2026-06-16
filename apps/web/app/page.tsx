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

      {/* Hero */}
      <header className="hero">
        <div className="container hero-grid">
          <div>
            <span className="pill">
              <span className="dot" />
              Private memory · powered by vector RAG
            </span>
            <h1>
              Tell it once.
              <br />
              <span className="amber">Ask it anytime.</span>
            </h1>
            <p className="lead">
              MyMemory is a personal memory store. Say or type anything you want
              to remember — a license plate, a friend&apos;s address, a Wi-Fi
              password — then just ask for it later, in plain language.
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

          {/* Faux chat demo */}
          <div className="demo">
            <div className="demo-head">
              <span className="lamp" style={{ background: "#d4694f" }} />
              <span className="lamp" style={{ background: "#e8a13c" }} />
              <span className="lamp" style={{ background: "#2f4a3a" }} />
              <span className="title">MYMEMORY</span>
            </div>
            <div className="bubbles">
              <div className="bubble user">My car license plate is 8XYZ123</div>
              <div className="bubble bot">
                <span className="tag">✓ Stored</span>
                Got it — I&apos;ll remember your license plate is 8XYZ123.
              </div>
              <div className="bubble user">What&apos;s my license plate?</div>
              <div className="bubble bot">
                <span className="tag">↩ Recalled</span>
                Your car license plate is <b>8XYZ123</b>.
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Features */}
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
              <div className="ico">🗣️</div>
              <h3>Just say it</h3>
              <p>
                Type or speak naturally. MyMemory figures out whether you&apos;re
                telling it something new or asking for it back.
              </p>
            </div>
            <div className="card">
              <div className="ico">🔎</div>
              <h3>Semantic recall</h3>
              <p>
                Ask in your own words. Vector search finds the right memory even
                when you don&apos;t use the exact phrasing you saved.
              </p>
            </div>
            <div className="card">
              <div className="ico">🔒</div>
              <h3>Yours alone</h3>
              <p>
                Every memory is scoped to your account. Answers are grounded only
                in what you&apos;ve saved — and cite their source.
              </p>
            </div>
            <div className="card">
              <div className="ico">🎙️</div>
              <h3>Voice-first</h3>
              <p>
                On the iOS app, speak hands-free with on-device transcription.
                The web app keeps the same fast chat experience.
              </p>
            </div>
            <div className="card">
              <div className="ico">📋</div>
              <h3>Browse anytime</h3>
              <p>
                Every fact you save shows up in a clean list. Review what
                MyMemory knows and delete anything with one tap.
              </p>
            </div>
            <div className="card">
              <div className="ico">⚡</div>
              <h3>Grounded answers</h3>
              <p>
                Built on Claude with retrieval-augmented generation — replies are
                drawn from your memories, not made up.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
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

      {/* CTA */}
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

      {/* Footer */}
      <footer>
        <div className="container footer">
          <span>© {2026} MyMemory — your private memory store.</span>
          <span>Built with FastAPI · pgvector · Claude on Bedrock</span>
        </div>
      </footer>
    </>
  );
}
