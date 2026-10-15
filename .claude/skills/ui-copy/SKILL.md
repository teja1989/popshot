---
name: ui-copy
description: Write or change words people see in Popshot (labels, buttons, empty states, notifications, emails, errors from the API). Use for any user-facing text so it stays friendly and consistent and passes the copy tests.
---

# UI copy

## Voice

- Friendly, short and plain, like a crewmate texting. One idea per sentence.
- Encouraging, never judging. A win comes first, then one thing to try. Nobody is behind,
  failing or weak.
- **No rankings.** Crew points help keep games even; they don't order people. Lists of
  people are A to Z.
- **No gendered guesses.** Use the person's name or "they". Never he, she, him, her, his
  or hers.
- Say **"crew"** in new copy (the tab is Crew). Some older screens still say "group".
- Don't say **"AI"** on screens. Where it matters (consent, the privacy page), name the
  provider ("Google Gemini") in a small note.
- Sentence case for buttons and headings ("Log a game", not "Log A Game").
- Count properly: "1 game", "2 games".
- Error messages say what happened and what to do next ("We couldn't load your crew just
  now." plus a "Try again" button). Never blame the person.
- Notifications name the crew and the event, and never someone's private data.

## Rules enforced by tests

`apps/web/src/lib/copy-rules.ts` has `BANNED`: words that shame, rank or guess gender. The copy
tests (`journey.test.ts`, `court-lines.test.ts`, `headlines.test.ts`) check copy lists
against it, and `court-lines.test.ts` fails if "AI" appears in screen copy.

When you add a list of lines (tips, headlines, notifications), add a test that runs it
through `BANNED` and any length limit. Then mutation-check it: put a banned word in, see the
test fail, take it out.

## Accessibility

- Every button and link has a name a screen reader can read. Icon-only controls get
  `aria-label`.
- Changing text such as the flipping headline is `aria-hidden`, with a steady version for
  screen readers.
- Don't rely on colour alone to say something.

## Where words live

- Short, screen-specific copy: in the component.
- Lists and rules: in `src/lib/` (`journey.ts`, `court-lines.ts`, `headlines.ts`).
- API messages: the `detail` of `HTTPException`s, shown to people as written.
- Legal pages: `src/app/privacy/page.tsx` and `src/app/terms/page.tsx`. Change them when what
  we keep or share changes.
