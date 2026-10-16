/** Follows who is signed in and loads their profile, for the app's sign-in state (components/auth.tsx). */

export const PROFILE_PROBLEM = "We couldn't load your profile just now. Try again in a moment.";

export type SignInState<U, M> =
  | { kind: "signed-out" }
  | { kind: "signed-in"; user: U; me: M | null; problem: string | null };

/**
 * Handles each sign-in change from `listen`: signed out, or signed in and then the profile from
 * `loadMe`. `switched` runs when the account changes (sign-out included), so answers kept for
 * the old account can be dropped. Returns the unsubscribe from `listen`.
 *
 * A profile answer that arrives after a sign-out or a switch belongs to someone else and is
 * dropped: applying it would put the old account back on screen.
 */
export function followSignIn<U extends { uid: string }, M>(
  listen: (next: (user: U | null) => void) => () => void,
  loadMe: (user: U) => Promise<M>,
  set: (state: SignInState<U, M>) => void,
  switched: () => void,
): () => void {
  let lastUid: string | null = null;
  let current: U | null = null;
  return listen((user) => {
    current = user;
    if (user?.uid !== lastUid) {
      switched();
      lastUid = user?.uid ?? null;
    }
    if (!user) {
      set({ kind: "signed-out" });
      return;
    }
    set({ kind: "signed-in", user, me: null, problem: null });
    loadMe(user).then(
      (me) => {
        if (current === user) set({ kind: "signed-in", user, me, problem: null });
      },
      () => {
        if (current === user) set({ kind: "signed-in", user, me: null, problem: PROFILE_PROBLEM });
      },
    );
  });
}
