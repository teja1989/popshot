## What and why

<!-- One or two sentences. One step per PR, branched from main. -->

## How it was tested

- [ ] Unit tests
- [ ] Database tests (required if data access changed: isolation list, the stranger and removed-member cases)
- [ ] Full-stack browser tests on desktop and phone (`./dev/run.sh e2e`) if signed-in screens changed
- [ ] Mutation-checked each new or changed guard (broke it, saw the test fail, put it back)
- [ ] Phone screenshots, light and dark, if something visible changed

## Checklist

- [ ] No secrets, keys, real config or personal data in the diff
- [ ] New tables have forced row-level security; crew tables have `group_id`, personal ones are owner-only (see the `new-migration` skill)
- [ ] Words follow the copy rules (`apps/web/src/lib/copy-rules.ts`, no "AI" on screens)
- [ ] New visible features are behind a switch
- [ ] Privacy page updated if what we keep or share changed
- [ ] Docs, AGENTS.md or ADRs updated if a decision or convention changed

## After deploy

<!-- What the plan should show (infra), and what to check on the live site. -->
