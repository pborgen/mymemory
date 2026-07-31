import Link from "next/link";

export default function NotFound() {
  return (
    <main className="container" style={{ padding: "80px 24px", textAlign: "center" }}>
      <h1 style={{ fontFamily: "var(--font-display)", fontSize: 36 }}>Not found</h1>
      <p style={{ color: "var(--text-dim)" }}>That page isn’t in this build.</p>
      <p style={{ marginTop: 24 }}>
        <Link href="/" className="btn btn-primary">
          Go home
        </Link>
      </p>
    </main>
  );
}
