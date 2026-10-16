import { describe, expect, it, vi } from "vitest";

import { followSignIn, PROFILE_PROBLEM, type SignInState } from "./auth-state";

interface FakeUser {
  uid: string;
}

/** A sign-in listener we drive by hand, and profile loads we answer by hand. */
function setup() {
  let emit: (user: FakeUser | null) => void = () => undefined;
  const unsubscribe = vi.fn();
  const loads: { user: FakeUser; resolve: (me: string) => void; reject: () => void }[] = [];
  const states: SignInState<FakeUser, string>[] = [];
  const switched = vi.fn();
  const stop = followSignIn<FakeUser, string>(
    (next) => {
      emit = next;
      return unsubscribe;
    },
    (user) =>
      new Promise<string>((resolve, reject) => {
        loads.push({
          user,
          resolve,
          reject: () => {
            reject(new Error("offline"));
          },
        });
      }),
    (state) => states.push(state),
    switched,
  );
  const load = (i: number) => {
    const found = loads[i];
    if (!found) throw new Error(`no profile load ${String(i)}`);
    return found;
  };
  return {
    emit: (user: FakeUser | null) => {
      emit(user);
    },
    load,
    states,
    switched,
    stop,
    unsubscribe,
  };
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
const last = <T>(list: T[]) => list[list.length - 1];

describe("followSignIn", () => {
  it("signs in, then shows the profile", async () => {
    const t = setup();
    const sam = { uid: "sam" };
    t.emit(sam);
    expect(last(t.states)).toEqual({ kind: "signed-in", user: sam, me: null, problem: null });
    t.load(0).resolve("Sam's profile");
    await flush();
    expect(last(t.states)).toEqual({ kind: "signed-in", user: sam, me: "Sam's profile", problem: null });
  });

  it("says so when the profile can't load", async () => {
    const t = setup();
    const sam = { uid: "sam" };
    t.emit(sam);
    t.load(0).reject();
    await flush();
    expect(last(t.states)).toEqual({ kind: "signed-in", user: sam, me: null, problem: PROFILE_PROBLEM });
  });

  it("stays signed out when the profile answers after signing out", async () => {
    const t = setup();
    t.emit({ uid: "sam" });
    t.emit(null);
    t.load(0).resolve("Sam's profile");
    await flush();
    expect(last(t.states)).toEqual({ kind: "signed-out" });
  });

  it("stays signed out when the profile fails after signing out", async () => {
    const t = setup();
    t.emit({ uid: "sam" });
    t.emit(null);
    t.load(0).reject();
    await flush();
    expect(last(t.states)).toEqual({ kind: "signed-out" });
  });

  it("keeps the new account when the old account's profile answers late", async () => {
    const t = setup();
    const ana = { uid: "ana" };
    t.emit({ uid: "sam" });
    t.emit(ana);
    t.load(1).resolve("Ana's profile");
    await flush();
    t.load(0).resolve("Sam's profile");
    await flush();
    expect(last(t.states)).toEqual({ kind: "signed-in", user: ana, me: "Ana's profile", problem: null });
  });

  it("drops remembered answers when the account changes, not when it stays", () => {
    const t = setup();
    const sam = { uid: "sam" };
    t.emit(sam);
    t.emit(sam);
    expect(t.switched).toHaveBeenCalledTimes(1);
    t.emit(null);
    expect(t.switched).toHaveBeenCalledTimes(2);
    t.emit({ uid: "ana" });
    expect(t.switched).toHaveBeenCalledTimes(3);
  });

  it("stops listening when asked", () => {
    const t = setup();
    t.stop();
    expect(t.unsubscribe).toHaveBeenCalledOnce();
  });
});
