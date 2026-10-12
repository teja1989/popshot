import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";

import { H2, LegalPage, List } from "@/components/legal-page";
import { LEGAL } from "@/lib/legal";

export const metadata: Metadata = { title: "Contact · Popshot" };

export default async function ContactPage() {
  // Rendered per request so its scripts get this request's CSP nonce.
  await connection();
  const email = <a href={`mailto:${LEGAL.contactEmail}`}>{LEGAL.contactEmail}</a>;
  return (
    <LegalPage title="Contact us">
      <p>
        Popshot is run by a small team at {LEGAL.company}. Email {email} and a real person will reply, usually within a
        few days.
      </p>

      <H2>Good things to include</H2>
      <List>
        <li>The name on your Popshot account and your crew&apos;s name, if it&apos;s about a group.</li>
        <li>What you expected and what happened, with a screenshot if you can.</li>
        <li>Please don&apos;t send passwords or anything you&apos;d rather keep private; we&apos;ll never ask.</li>
      </List>

      <H2>Common requests</H2>
      <List>
        <li>
          <strong>A group without a lead</strong> (say, they&apos;ve left the app): we can make another member the lead.
        </li>
        <li>
          <strong>Your data:</strong> a copy, a correction, or deleting your account. See the{" "}
          <Link href="/privacy">privacy policy</Link> for what that covers.
        </li>
        <li>
          <strong>Something unkind or wrong in a group:</strong> tell us the group and what happened.
        </li>
        <li>
          <strong>A security problem:</strong> email with &ldquo;Security&rdquo; in the subject. Please give us a chance
          to fix it before telling others.
        </li>
      </List>
    </LegalPage>
  );
}
