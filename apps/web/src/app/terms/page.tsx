import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";

import { H2, LegalPage, List } from "@/components/legal-page";
import { LEGAL } from "@/lib/legal";

export const metadata: Metadata = { title: "Terms · Popshot" };

export default async function TermsPage() {
  // Rendered per request so its scripts get this request's CSP nonce.
  await connection();
  return (
    <LegalPage title="Terms of use">
      <p>
        These terms are an agreement between you and {LEGAL.company} (&ldquo;we&rdquo;), which runs Popshot. By using
        Popshot you agree to them and to our <Link href="/privacy">privacy policy</Link>.
      </p>

      <H2>Who can use Popshot</H2>
      <p>
        You need to be 13 or older, and old enough where you live to agree to these terms (or have a parent or guardian
        agree for you). You sign in with your Google account and are responsible for what happens under it.
      </p>

      <H2>Playing fair</H2>
      <List>
        <li>Be kind. No harassment, hate, threats or anything sexual.</li>
        <li>Only add people to games who actually played, and use names they&apos;re happy with.</li>
        <li>Don&apos;t pretend to be someone else or log games you know are false.</li>
        <li>
          Don&apos;t break, overload, scrape or get around the security of Popshot, or get into groups you weren&apos;t
          invited to.
        </li>
      </List>
      <p>
        Group leads choose who joins and can remove members. We can remove content or suspend accounts that break these
        terms.
      </p>

      <H2>Your content</H2>
      <p>
        What you add stays yours. You give us permission to store and show it to the people it&apos;s meant for (your
        crew), only to run Popshot. That permission ends when the content is deleted, apart from short-lived backups.
      </p>

      <H2>Stats are for fun</H2>
      <p>
        Crew points, ratings and stats are friendly estimates from the games your crew logs. They aren&apos;t official
        ratings and may change as we improve how they&apos;re worked out.
      </p>

      <H2>Play safe</H2>
      <p>
        Pickleball is a physical sport. You play at your own risk; Popshot only keeps the score. Check with a doctor
        before starting if you&apos;re unsure, and look after yourself and the people you play with.
      </p>

      <H2>The service</H2>
      <p>
        Popshot is free today. If we add paid features, they&apos;ll come with clear prices and their own terms, and
        nothing you use for free now will start costing money without you choosing it. We may change or stop parts of
        Popshot; if we shut it down, we&apos;ll give at least 30 days&apos; notice so you can get a copy of your data.
      </p>

      <H2>No warranties</H2>
      <p>
        Popshot is provided &ldquo;as is&rdquo;. We work hard to keep it running and your data safe, but we can&apos;t
        promise it will always be available, error-free or that data will never be lost.
      </p>

      <H2>Limits on liability</H2>
      <p>
        To the extent the law allows, we aren&apos;t liable for indirect or consequential losses, and our total
        liability for any claim about Popshot is limited to $100 or what you paid us in the past 12 months, whichever is
        more. Some places don&apos;t allow these limits, so they may not apply to you.
      </p>

      <H2>Ending</H2>
      <p>
        You can stop using Popshot at any time and ask us to delete your account. We can suspend or close accounts that
        break these terms.
      </p>

      <H2>Changes and law</H2>
      <p>
        If we change these terms in a way that matters, we&apos;ll say so in the app before it takes effect; using
        Popshot after that means you accept them. These terms are governed by the laws of {LEGAL.state}, USA, and
        disputes go to its courts, unless the law where you live says otherwise.
      </p>
      <p>
        Questions? See the <Link href="/contact">contact page</Link>.
      </p>
    </LegalPage>
  );
}
