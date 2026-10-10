import Link from "next/link";
import { connection } from "next/server";

export default async function NotFound() {
  // Rendered per request so its scripts get this request's CSP nonce.
  await connection();
  return (
    <main className="page">
      <section className="card">
        <h1>That page is out of bounds.</h1>
        <p className="lede">The link may be old, or the page may have moved.</p>
        <Link className="button" href="/">
          Back to Popshot
        </Link>
      </section>
    </main>
  );
}
