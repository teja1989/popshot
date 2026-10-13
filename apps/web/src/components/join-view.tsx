"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { apiPost, ApiError } from "@/lib/api-client";
import { tokenFromHash, type InvitePreview, type Joined } from "@/lib/invites";

import { useSignedIn } from "./auth";
import { CrewProfileSummary } from "./crew-profile-summary";
import { buttonClass } from "./ui/button";
import { CourtPattern } from "./ui/court-pattern";

type State =
  | { kind: "no-link" }
  | { kind: "loading"; token: string }
  | { kind: "dead" }
  | { kind: "failed"; token: string }
  | { kind: "ready"; token: string; preview: InvitePreview };


export function JoinView() {
  const { user } = useSignedIn();
  const router = useRouter();
  const [state, setState] = useState<State>(() => {
    const token = tokenFromHash(window.location.hash);
    return token ? { kind: "loading", token } : { kind: "no-link" };
  });
  const [joining, setJoining] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const token = state.kind === "loading" ? state.token : null;

  // Once read, take the token out of the address bar so it doesn't linger in the browser's
  // history, a screenshot or a shared screen. Opening another invite link in this tab only
  // changes the fragment, so read that one too.
  useEffect(() => {
    function clearHash() {
      if (window.location.hash) {
        window.history.replaceState(null, "", window.location.pathname + window.location.search);
      }
    }
    function onHashChange() {
      const next = tokenFromHash(window.location.hash);
      clearHash();
      if (next) {
        setProblem(null);
        setState({ kind: "loading", token: next });
      }
    }
    clearHash();
    window.addEventListener("hashchange", onHashChange);
    return () => {
      window.removeEventListener("hashchange", onHashChange);
    };
  }, []);

  useEffect(() => {
    if (token === null) {
      return;
    }
    let current = true;
    apiPost<InvitePreview>(user, "/v1/invites/preview", { token })
      .then((preview) => {
        if (current) {
          setState({ kind: "ready", token, preview });
        }
      })
      .catch((error: unknown) => {
        if (current) {
          setState(error instanceof ApiError && error.status === 404 ? { kind: "dead" } : { kind: "failed", token });
        }
      });
    return () => {
      current = false;
    };
  }, [user, token]);

  async function join(joinToken: string) {
    setJoining(true);
    setProblem(null);
    try {
      const joined = await apiPost<Joined>(user, "/v1/invites/join", { token: joinToken });
      if (joined.group_id) {
        router.push(`/groups/${joined.group_id}`);
        return;
      }
      setProblem("You can't join this group with this link. Ask its lead.");
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setState({ kind: "dead" });
      } else {
        setProblem("We couldn't send your request just now. Try again in a moment.");
      }
    } finally {
      setJoining(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-5 px-5 pt-8 pb-12 lg:pt-14">
      {state.kind === "loading" && <p className="text-muted">Opening your invite…</p>}

      {state.kind === "no-link" && (
        <Message title="Open your invite link again.">
          This page needs the whole link you were sent. Tap it again, or ask the group&apos;s lead
          for a new one.
        </Message>
      )}

      {state.kind === "dead" && (
        <Message title="This invite link isn't valid any more.">
          It may have expired, been used, or been cancelled. Ask the group&apos;s lead for a new one.
        </Message>
      )}

      {state.kind === "failed" && (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-2xl border border-line bg-surface p-5">
          <p>We couldn&apos;t open this invite just now.</p>
          <button
            type="button"
            className={buttonClass("quiet")}
            onClick={() => {
              setState({ kind: "loading", token: state.token });
            }}
          >
            Try again
          </button>
        </div>
      )}

      {state.kind === "ready" && (
        <section className="relative isolate flex animate-rise flex-col gap-5 overflow-hidden rounded-[28px] bg-hero p-6 text-on-hero lg:p-8">
          <CourtPattern />
          <p className="text-meta font-bold tracking-[0.14em] text-ball uppercase">
            {state.preview.invited_by} invited you
          </p>
          <h1 className="text-display-sm leading-[1.05] font-extrabold tracking-[-0.02em] break-words font-display">
            {state.preview.group_name}
          </h1>
          <CrewProfileSummary profile={state.preview} onHero />
          <Outcome
            preview={state.preview}
            joining={joining}
            onJoin={() => void join(state.token)}
          />
          <p role="alert" className="text-body font-bold text-ball empty:hidden">
            {problem}
          </p>
        </section>
      )}
    </main>
  );
}

function Outcome({
  preview,
  joining,
  onJoin,
}: {
  preview: InvitePreview;
  joining: boolean;
  onJoin: () => void;
}) {
  const groupLink = preview.group_id ? `/groups/${preview.group_id}` : null;
  if (preview.my_status === "active" && groupLink) {
    return (
      <>
        <p className="text-lead text-on-hero-muted">You&apos;re already in this group.</p>
        <Link href={groupLink} className={buttonClass("action", "h-14")}>
          Open the group
        </Link>
      </>
    );
  }
  if (preview.my_status === "pending" && groupLink) {
    return (
      <>
        <p className="text-lead text-on-hero-muted">
          You&apos;ve asked to join. The lead or a co-lead will let you in.
        </p>
        <Link href={groupLink} className={buttonClass("action", "h-14")}>
          See your request
        </Link>
      </>
    );
  }
  if (preview.my_status === "removed") {
    return (
      <p className="text-lead text-on-hero-muted">
        You can&apos;t join this group with this link. Ask its lead if you think that&apos;s a mistake.
      </p>
    );
  }
  return (
    <>
      <p className="text-lead text-on-hero-muted">
        Ask to join and the group&apos;s lead will approve you. Until then, only your name and
        photo are shared with them.
      </p>
      <button type="button" className={buttonClass("action", "h-14")} onClick={onJoin} disabled={joining}>
        {joining ? "Sending…" : "Ask to join"}
      </button>
    </>
  );
}

function Message({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5">
      <h1 className="text-title-lg font-extrabold font-display">{title}</h1>
      <p className="text-muted">{children}</p>
    </section>
  );
}
