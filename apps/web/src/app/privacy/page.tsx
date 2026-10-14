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
          <strong>What you add:</strong> the groups you start or join (and a group&apos;s profile: its about, usual
          times and home courts), invites, games (players, scores, rules and when they were played), meetups (time,
          venue, note, who&apos;s going), your playing level, the focus areas and game notes you pick, and your
          notification choices.
        </li>
        <li>
          <strong>Your journey:</strong> the story you write in your own words (how you started, what you&apos;re good
          at, what you&apos;re working on, a goal) and your learning notes. Each time you update your story we keep the
          earlier version too, so you can look back on how your game has grown. It&apos;s in your data download and
          deleted with your account.
        </li>
        <li>
          <strong>Invites:</strong> your Popshot code (a random code you can change any time), invites crews send you
          and how you answered, crews you&apos;ve stopped from inviting you, and when leads looked codes up (to limit
          how often they can, so codes can&apos;t be guessed).
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
          <strong>Where you came from:</strong> if you arrive through an invite link or a tagged link (for example from
          a shared recap or a poster), your browser remembers that one word, such as &ldquo;recap&rdquo; or
          &ldquo;invite&rdquo;, and sends it once when you first sign up. It&apos;s kept with your account, only our
          staff see it (as totals, to learn which ways of finding Popshot work), it&apos;s in your data download, and
          it&apos;s deleted with your account.
        </li>
        <li>
          <strong>Visit counts:</strong> we count visits to the home page, invite pages and shared recaps, per day and
          per tag. Only the totals are kept: nothing about who visited, no IP address, no cookie.
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
        <li>To run Popshot: show games, stats, crew points and meetups to your crew, and send reminders.</li>
        <li>To keep it safe and working: stopping abuse, fixing problems, and helping when you contact us.</li>
        <li>To understand use in totals, like how many people played this week.</li>
      </List>
      <p>We don&apos;t sell your data, share it for advertising, show ads, or use it to train AI models.</p>

      <H2>Who can see what</H2>
      <List>
        <li>
          <strong>Your crew:</strong> people in a group see each member&apos;s name, photo, games, crew points and
          meetup answers in that group. Groups are private: nobody outside one can find or see it, except a recap
          someone in it shares (below).
        </li>
        <li>
          <strong>Only you:</strong> your focus areas, game notes, journey story and learning notes.
        </li>
        <li>
          <strong>People invited to a group:</strong> see its name, its about and usual play times, and who invited
          them. Its home courts and members stay hidden until they join.
        </li>
        <li>
          <strong>Invites:</strong> there&apos;s no search for people on Popshot. A crew&apos;s lead or co-lead can
          invite you only if you&apos;ve been in a crew together, or if you gave them your Popshot code. With your code
          they see your first name and photo, to check it&apos;s you. You decide whether to join. If you say no, they
          aren&apos;t told, and you can stop that crew from inviting you again.
        </li>
        <li>
          <strong>Shared recap links:</strong> anyone in a crew can share an outing&apos;s recap as a link. Anyone with
          the link can see that one recap, without signing in: the crew&apos;s name, first names, scores and awards, but
          not where you played. Links stop working after 30 days, and whoever shared one, or the crew&apos;s lead or a
          co-lead, can turn it off sooner. If you&apos;d rather not be named, turn off &ldquo;Show my first name&rdquo;
          on your You page and you&apos;ll show as &ldquo;Crew member&rdquo;. Guests added by name can&apos;t change
          this themselves; ask your lead to rename a guest.
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
        <li>
          <strong>Recaps written by AI:</strong> after an outing, Google&apos;s Gemini AI (through Google Cloud, in the
          United States) may write the recap&apos;s headline and lines. It gets first names and that outing&apos;s game
          facts (games played and awards), nothing else. Google doesn&apos;t use it to train its models, and may keep it
          in memory for up to 24 hours. These recaps are labelled &ldquo;Written with Google Gemini&rdquo;.
        </li>
        <li>
          <strong>Personal journey check-ins, written by AI:</strong> only if you say yes on your Journey tab (and you
          can turn it off there any time), Google&apos;s Gemini AI writes your check-ins. It gets your first name, that
          fortnight&apos;s games (counts, wins, crews and partners&apos; first names), what you ticked after games, your
          learning notes, and your goal and what you&apos;d like to get better at, nothing else. The same Google terms
          apply. Without your yes, Popshot writes them itself and nothing is sent.
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
        You can change your name and level in the app, turn notifications off, keep your name off shared recaps, change
        your Popshot code, stop a crew from inviting you, and leave any group. On your You page you can download a copy
        of your data and delete your account. Deleting has a 7-day window to change your mind; after that your sign-in,
        name, photo, notes, settings and devices are deleted for good. Your name and photo are removed from your
        groups&apos; games and you show as &ldquo;Former player&rdquo;; the scores stay, so your crew&apos;s history
        still adds up. If you lead a group with other members, make someone else the lead first. For anything else, such
        as correcting your data, email {email}. We&apos;ll confirm it&apos;s you and reply within 30 days.
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
