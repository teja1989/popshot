---
name: feature-switch
description: Put a new or changing feature behind a switch an admin can turn on per crew, for everyone, or off (features table, migration 0027). Use whenever a change is visible to people, so it can be rolled out gradually and turned off without a deploy.
---

# Feature switch

Admins flip switches on the admin Features page (`/admin/features`), with a reason, and every
change is logged. Nothing is cached, so a change applies on the next request. Read
`services/api/migrations/versions/0027_feature_switches.py` first: its docstring explains the
rules.

## 1. Pick the key and kind

- **Key:** `area.name`, lowercase (`events.shuffle`, `recaps.ai`, `crew.open`). The area must
  be one the table allows: events, learn, recaps, courts, crew, play, home, you. A new area
  means changing that `CHECK` in your migration.
- **Kind:**
  - **Per crew** (most features): on for a crew when rollout is `everyone`, or `crews` and the
    crew is on the list.
  - **Per person** (area `you`): `app_feature_on_for_me(key)`. On with `everyone`, or `crews`
    and you're active in a listed crew.
- **`needs_plan = 'organizer'`** only if it's part of a paid plan.

## 2. Add the row in your migration

```sql
INSERT INTO features (key, area, title, description, needs_plan, rollout) VALUES
    ('crew.open', 'crew', 'Open crews', 'Leads can open a crew so anyone on Popshot can join.',
     NULL, 'off');
```

Start with `'off'` or `'crews'`, never `'everyone'` for something new. `downgrade()` deletes
the row (`DELETE FROM features WHERE key = ...`).

## 3. Check it in the API

- **Per crew:** `feature_on(session, key, group_id)` from `routes/features.py`.
- **Per person:** `SELECT app_feature_on_for_me(:key)`.

The API always checks, whatever the web shows. While a switch is off:
- a feature that's hidden altogether answers **404**, as if it didn't exist (journey,
  `require_journey` in `routes/journey.py`);
- an action on something people can see answers **403** with a friendly message ("… isn't
  switched on for this crew yet.", `routes/events.py`).

## 4. Check it in the web app

From `src/components/features.tsx`:
- `useFeature(key, crewId)` for a crew's screen;
- `useYouFeature(key)` for a person's;
- `useEverywhere()` for tabs and menus (on in at least one of your crews).

Hide the feature until the answer has loaded (`useFeaturesLoaded()`). A tab can carry
`feature: "key"` in `src/lib/nav.ts`.

## 5. Test both ways

- **API** (`tests/db/test_features.py` style): off → refused; on for crew A → works for A,
  still refused for crew B.
- **e2e:** with the switch off the feature isn't there. To show it on, either switch it on for
  the test's crew through the admin API, or stand in for `/api/v1/me/features` with
  `page.route` (see "a tab behind a feature switch" in `e2e/full/navigation.spec.ts`).
- **Mutation-check the API guard:** remove the check, see the off test fail, put it back.

## 6. After deploy

Say in the PR which switch it is, its starting rollout, and how to turn it on for one crew
first.
