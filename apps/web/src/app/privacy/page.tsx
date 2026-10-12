import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";

import { H2, LegalPage, List } from "@/components/legal-page";
import { LEGAL } from "@/lib/legal";

export const metadata: Metadata = { title: "Privacy · Popshot" };

export default async function PrivacyPage() {
  // Rendered per request so its scripts get this request's CSP nonce.
  await connection();
  const email = <a href={`mailto:${LEGAL.contactEmail}`}>{LEGAL.contactEmail}</a>;
  return (
    <LegalPage title="Privacy policy">
      <p>
        Popshot keeps score for pickleball crews. It&apos;s run by {LEGAL.company} (&ldquo;we&rdquo;). This page says
        what we collect, why, who can see it, and how to get it changed or deleted. The short version: your crew sees
        your games, nobody else does, and we don&apos;t sell or advertise with your data.
      </p>

      <H2>What we collect</H2>
      <List>
        <li>
          <strong>From Google when you sign in:</strong> your name, profile photo link and a Google account ID. Google
          (Firebase Authentication) handles the sign-in and keeps your email address; our database doesn&apos;t store
          it.
        </li>
        <li>
          <strong>What you add:</strong> the groups you start or join, invites, games (players, scores, rules and when
          they were played), play nights (time, venue, note, who&apos;s going), your playing level, the focus areas and
          game notes you pick, and your notification choices.
        </li>
        <li>
          <strong>Names you add for others:</strong> when you add a guest to a game, the name you type is kept in that
          group, so please use names your crew would recognise and nothing more.
        </li>
        <li>
          <strong>Notifications:</strong> if you turn them on, your browser gives us an address and keys to send
          notifications to that device.
        </li>
        <li>
          <strong>Usage:</strong> which days you opened Popshot (to count active players), and server logs of requests
          (the page or action, the result and how long it took). Our hosting provider&apos;s logs can include your IP
          address and browser type.
        </li>
        <li>
          <strong>On your device:</strong> your chosen theme, group and games view are saved in your browser, and
          Google&apos;s sign-in keeps you signed in there. We don&apos;t use advertising or tracking cookies.
        </li>
      </List>

      <H2>How we use it</H2>
      <List>
        <li>To run Popshot: show games, stats, crew points and play nights to your crew, and send reminders.</li>
        <li>To keep it safe and working: stopping abuse, fixing problems, and helping when you contact us.</li>
        <li>To understand use in totals, like how many people played this week.</li>
      </List>
      <p>We don&apos;t sell your data, share it for advertising, show ads, or use it to train AI models.</p>

      <H2>Who can see what</H2>
      <List>
        <li>
          <strong>Your crew:</strong> people in a group see each member&apos;s name, photo, games, crew points and play
          night answers in that group. Groups are private: nobody outside one can find or see it.
        </li>
        <li>
          <strong>Only you:</strong> your focus areas and game notes.
        </li>
        <li>
          <strong>Popshot support:</strong> a small number of our staff can look up an account or group, and its email
          address from Google, to help with a problem. Every lookup and change they make is recorded.
        </li>
        <li>
          <strong>Service providers:</strong> Google Cloud hosts Popshot and its database in the United States, Google
          Firebase handles sign-in, and your browser&apos;s push service (from Google, Apple or Mozilla) delivers
          notifications. They handle data only to provide those services.
        </li>
        <li>We&apos;ll share data if the law requires it, and only what&apos;s required.</li>
      </List>

      <H2>How long we keep it</H2>
      <List>
        <li>Your account and what you add: until you delete it or ask us to.</li>
        <li>A deleted group: its lead can restore it for 30 days, then it&apos;s deleted for good.</li>
        <li>Which days you used Popshot: 13 months.</li>
        <li>Backups: up to 7 days. Server logs: about 30 days.</li>
      </List>

      <H2>Your choices and rights</H2>
      <p>
        You can change your name and level in the app, turn notifications off, and leave any group. To get a copy of
        your data, correct it, or delete your account, email {email}. We&apos;ll confirm it&apos;s you and reply within
        30 days. Deleting your account removes your name and photo from your groups&apos; games; the scores stay, so
        your crew&apos;s history still adds up.
      </p>
      <p>
        Depending on where you live (for example California or the EU), you may have further rights, such as to know
        what we hold or to object to how we use it. We honour these requests the same way. We don&apos;t sell or share
        personal information as California law defines it.
      </p>

      <H2>Children</H2>
      <p>
        Popshot is for people 13 and older. If you believe a child under 13 has an account, tell us and we&apos;ll
        delete it.
      </p>

      <H2>Security</H2>
      <p>
        Data travels encrypted, each group&apos;s data is walled off from every other group in the database, and our
        systems get only the access they need. No system is perfectly secure; if something goes wrong that affects you,
        we&apos;ll tell you.
      </p>

      <H2>Changes</H2>
      <p>
        If we change this policy in a way that matters, we&apos;ll say so in the app before it takes effect. Questions?
        See the <Link href="/contact">contact page</Link> or email {email}.
      </p>
    </LegalPage>
  );
}
