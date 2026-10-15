# 0006: Five tabs, one tab per screen, settings under You

- Status: accepted
- Date: 2026-10-15

## Context

The menu had grown to six tabs (Home, Play, Crew, Learn, You, More), and More had become a
17-item list of everything that didn't fit elsewhere. We're adding discovery (open crews near
you), and we plan to ship Android and iOS apps later. Both platforms' guidelines recommend
three to five destinations in a tab bar, and native tab bars give each tab its own back
stack.

## Decision

1. **At most five tabs:** Home · Play · Find · Crew · You. Find shows only while its feature
   switch (`crew.open`) is on, so today most people see four.
2. **Every screen belongs to exactly one tab** (`lib/nav.ts`), which stays lit while you're on
   it, so a deep link opens in the right tab:
   - Home: `/`
   - Play: `/play`, and a crew's events, game log, meetups and game edits
     (`/groups/<id>/events|log|nights|matches/...`)
   - Find: `/find`
   - Crew: `/crew`, and the rest of `/groups/<id>/...` (crew page, members, settings, recaps)
   - You: `/you`, `/you/journey`, `/you/settings`
3. **No catch-all tab.** Settings (notifications, invite code, shared recaps, appearance, your
   data, help and legal, sign out) live at You → Settings, where apps keep them. `/more`
   redirects there.
4. **A new feature joins an existing tab.** A sixth destination means replacing one, decided
   in a new ADR, not appending.
5. **Actions stay where you are:** "Log a game" is a floating button (a top-bar "+" on iOS),
   and forms open in bottom sheets, which match native sheets.

## Consequences

- Moving to native apps keeps the same tabs, routes and deep links; only the shell changes.
  The approach (wrapping the web app or a native UI) is still open.
- Learn, when it arrives, lives inside You → Journey rather than as a tab.
- More's search and "New" markers are gone; with fewer, clearer places they earned little.
