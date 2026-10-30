# Help & Support: Ticket Frontend (Learner + Staff)

Date: 2026-10-30
Status: Draft for review
Backend: `apps/api` `/api/v1/tickets` (complete, tested; see "Backend contract")

## 1. Goal

Let learners raise support tickets and follow them to resolution, and let org
staff triage and resolve them, inside the LearnHouse web app, matching the
existing LearnHouse look and code conventions.

**Success looks like:** the full flow that was verified by hand in Postman
(raise, staff reply, internal note, resolve with note, learner sees the note but
not the internal note, learner reply reopens, close blocks replies) works end to
end through the UI with no API calls made by hand.

### In scope
- Learner `/help` page: **My Tickets** and **Raise a Ticket** tabs, ticket
  detail with thread, replies.
- Staff `/dash/support` page: filterable queue, ticket detail, triage
  (status, priority, assign to me), replies with internal notes, Resolve and
  Close actions.
- Shared data layer (service, query hooks, query keys) and en locale strings.
- One-word fix to the shared request helper so PATCH sends its body.

### Out of scope (later rounds)
- FAQ / troubleshooting guides (the `/help` tab bar is built so a FAQ tab can be
  added without restructuring).
- Email or in-app notifications on ticket updates.
- Attachments on tickets or messages.
- Assigning to someone other than yourself from the UI (the API supports it;
  the UI offers "Assign to me" and "Unassign" only).
- Translations beyond `en.json`.

## 2. Backend contract (already built)

Base: `${getAPIUrl()}tickets` (`getAPIUrl()` already ends in `/api/v1/`).

| Method | Path | Who | Returns |
|---|---|---|---|
| POST | `tickets/` | org member | `SupportTicketRead` |
| GET | `tickets/org/{orgId}/me` | org member | `SupportTicketRead[]` |
| GET | `tickets/{uuid}` | owner or staff | `SupportTicketDetail` (internal notes only for staff) |
| POST | `tickets/{uuid}/messages` | owner or staff | `TicketMessageRead` |
| GET | `tickets/org/{orgId}/admin?status&priority&category&assigned_to&page&limit` | staff | `{ items, total, page, limit }` |
| PATCH | `tickets/{uuid}` | staff | `SupportTicketRead` |

Behaviours the UI relies on:
- New tickets are always `OPEN` / `MEDIUM`; learners cannot set priority.
- A learner reply on a `RESOLVED` ticket sets it back to `OPEN`.
- Any reply to a `CLOSED` ticket returns **409**.
- Staff = org admin or maintainer (or superadmin). Non-staff get **403** on the
  queue and **404** on PATCH.
- `PATCH` with `"assigned_to": null` unassigns; omitting the field leaves it.
- Validation: subject 3–200 chars, description 10–10,000, message 1–10,000.

## 3. Learner experience: `/help`

**Route:** `app/orgs/[orgslug]/(withmenu)/help/`
- `page.tsx`: server component; `generateMetadata` ("Help & Support | {org}"),
  renders `<Help orgslug=... />`. Same shape as `trail/page.tsx`.
- `help.tsx`: client component.
- `loading.tsx`: skeleton, as `trail/loading.tsx`.

**Navigation:** two entry points, both shown only to signed-in users:
- An icon button (`Lifebuoy`, `@phosphor-icons/react`) in `OrgMenu.tsx` next to
  the existing Progress/Trail icon, wrapped in
  `AuthenticatedClientElement checkMethod="authentication"` with a tooltip, same
  markup as the Trail button.
- A "Help & Support" item in the profile dropdown in
  `components/Security/HeaderProfileBox.tsx`, after "Purchases".

Not added to `OrgMenuLinks.tsx`: that menu is driven by org feature flags and
per-org custom menu config, so a new builtin would be hidden for orgs with a
custom menu and would need a new feature key.

**Signed-out visitors:** the page shows a short "Sign in to contact support"
message with a sign-in link instead of the tabs.

**Layout:** `GeneralWrapperStyled` + `TypeOfContentTitle` ("Help & Support"),
then a tab bar (`components/ui/tabs`) with:

### 3.1 My Tickets (default tab)
- List of ticket cards, newest first. Each card: subject, status badge,
  category label, linked course name (if any), "Updated {relative time}",
  message count.
- Empty state: icon + "You haven't raised any tickets yet" + button to the Raise
  a Ticket tab.
- Clicking a card opens the **ticket detail** in place (list collapses to a
  "Back to my tickets" link). The open ticket is reflected in the URL as
  `?ticket={uuid}` so it survives refresh and can be linked to.

### 3.2 Ticket detail (learner)
- Header: subject, status badge, category, course, created date.
- Original description.
- **Resolution box** (green, only when `resolution_note` is set):
  "Resolution" + the note.
- Thread: messages oldest first. Staff replies (`is_staff`) are visually
  distinguished (label "Support team", tinted background); the learner's own
  messages are plain. Author avatar + name + time on each.
- Reply box (textarea + Send):
  - `OPEN` / `IN_PROGRESS`: normal.
  - `RESOLVED`: helper text "Still having trouble? Replying will reopen this
    ticket."
  - `CLOSED`: reply box replaced by "This ticket is closed. Raise a new ticket
    if you still need help." + button.

### 3.3 Raise a Ticket
Form fields:
- **Subject** (text input, required, 3–200).
- **Category** (select: Technical, Course content, Billing, Account, Other;
  default Technical).
- **Related course** (optional select of the org's courses, from the existing
  courses query; "None" default).
- **Description** (textarea, required, 10–10,000, with a character hint).

Behaviour:
- Client-side validation mirrors the backend limits; Submit disabled while
  invalid or submitting.
- On success: toast "Ticket submitted", switch to My Tickets with the new ticket
  open, form reset.
- On error: toast with the backend message (via `errorHandling`).

## 4. Staff experience: `/dash/support`

**Route:** `app/orgs/[orgslug]/dash/support/`
- `page.tsx`: server component with `generateMetadata`
  ("Support | {org}", `robots: noindex`), resolves `org.id`, renders client.
- `client.tsx`: client component.
- `page.search.ts`: command-palette entry (`id: 'dash.support'`,
  `href: '/dash/support'`, `group: 'navigation'`, icon `Lifebuoy`).

**Navigation:** add "Support" to `DashLeftMenu.tsx` and `DashMobileMenu.tsx`
next to Communities.

**Access:** the dash layout already requires dashboard access. If the queue
request returns 403 (e.g. an instructor without admin/maintainer role), the page
shows "Support tickets are available to organization admins and maintainers."
No other content is rendered.

**Layout:** matches `dash/communities/client.tsx`: `bg-[#f8f8f8]` page,
`Breadcrumbs` ("Support"), `text-3xl font-bold` title. Below it a two-pane view
on `lg` and up (queue left ~40%, detail right); on smaller screens the detail
replaces the queue with a back link. Selected ticket is kept in
`?ticket={uuid}`.

### 4.1 Queue
- Filter bar: Status (All / Open / In progress / Resolved / Closed; default
  **Open**), Priority (All / Low / Medium / High / Urgent), Category (All / …),
  and an "Assigned to me" toggle. Filters live in the URL query string so the
  view is shareable and survives refresh.
- Rows: subject, learner name, category, priority badge, status badge, assignee
  avatar (or "Unassigned"), relative age (`formatRelative`).
- Pagination: 25 per page, Previous / Next with "Showing 1–25 of N".
- Empty state per filter: "No {status} tickets".

### 4.2 Ticket detail (staff)
- Header: subject, learner (avatar, name, username), course, created date.
- **Triage bar** (each change saves immediately via PATCH, with a toast):
  - Status select.
  - Priority select.
  - "Assign to me" / "Unassign" button; shows current assignee.
- Description, resolution box (if set), thread. Internal notes have an amber
  background and an "Internal" label.
- Reply box with an **Internal note** toggle (off by default). When on, the box
  turns amber and the button reads "Add internal note".
- **Resolve** button (primary, black pill): opens a `components/ui/dialog` with
  a required "Resolution note" textarea, prefilled with the existing note if
  any. Confirm sends `PATCH { status: "RESOLVED", resolution_note }`.
- **Close** button (secondary): confirmation dialog, then
  `PATCH { status: "CLOSED" }`. On a closed ticket this becomes **Reopen**
  (`PATCH { status: "OPEN" }`).
- When the ticket is `CLOSED` the reply box is disabled with the same message
  learners see.

## 5. Data layer

### 5.1 Shared helper fix
`services/utils/ts/requests.ts`, `RequestBodyWithAuthHeader`: include
`'PATCH'` in the methods that send a JSON body. Today PATCH bodies are silently
dropped (the backend would receive an empty update and still return 200). No
existing caller sends PATCH through this helper (`services/ai/ai.ts` and
`services/billing/packs.ts` build their own PATCH requests), so nothing else
changes.

### 5.2 `services/tickets/tickets.ts`
- Types mirroring the backend: `TicketStatus`, `TicketPriority`,
  `TicketCategory` (string unions), `TicketAuthor`, `TicketCourseRef`,
  `SupportTicket`, `TicketMessage`, `SupportTicketDetail`,
  `SupportTicketPage`, `SupportTicketCreate`, `SupportTicketUpdate`,
  `TicketQueueFilters`.
- Reads (used by hooks): `getMyTickets(orgId, token)`,
  `getTicket(uuid, token)`, `getSupportQueue(orgId, filters, token)`.
- Writes: `createTicket(data, token)`,
  `replyToTicket(uuid, { content, is_internal }, token)`,
  `updateTicket(uuid, data, token)`.
- All use `RequestBodyWithAuthHeader` + `errorHandling`, as
  `services/communities/communities.ts` does.

### 5.3 `lib/tickets/` (pure, unit-tested)
- `labels.ts`: status / priority / category to i18n key and badge colour
  (e.g. OPEN blue, IN_PROGRESS amber, RESOLVED green, CLOSED gray; URGENT red,
  HIGH orange, MEDIUM gray, LOW slate).
- `filters.ts`: `queryToFilters(searchParams)` (parses and validates URL
  params, falls back to defaults on junk), `filtersToSearchParams(filters)`
  (the dash page URL) and `filtersToApiQuery(filters, userId)` (the API query
  string: drops "All", maps "Assigned to me" to `assigned_to`, adds page/limit).
- `validation.ts`: `validateTicketForm(values)` returning per-field error keys,
  using the same limits as the backend.
- Relative times ("3 hours ago") use the existing `formatRelative` from
  `lib/format.ts`; no new time helper.

### 5.4 Query hooks: `hooks/queries/useTickets.ts`
- `useMyTickets(orgId)`, `useTicket(uuid)`, `useSupportQueue(orgId, filters)`,
  modelled on `useTrail.ts` (token from `useLHSession`, `enabled` guards,
  `staleTime: 30_000`).
- Keys added to `lib/query/keys.ts`:
  `tickets: { mine: (orgId), detail: (uuid), queue: (orgId, filters) }`.
- Mutations are plain service calls followed by `invalidateQueries` on the
  affected keys: create invalidates `mine`; reply invalidates `detail` (and
  `mine` / `queue`, since status and counts can change); update invalidates
  `detail` and `queue`.

### 5.5 Strings
All user-facing text in `locales/en.json` under `help.*` (learner) and
`dashboard.support.*` (staff), plus `common`-style keys for status, priority
and category labels under `tickets.*` so both sides share them.

## 6. Components

Kept small and single-purpose under `components/Pages/Help/` (learner) and
`components/Dashboard/Pages/Support/` (staff), sharing a few pieces in
`components/Objects/Tickets/`:

Shared (`components/Objects/Tickets/`):
- `TicketStatusBadge`, `TicketPriorityBadge`
- `TicketThread` (messages list; prop `showInternal`)
- `TicketReplyBox` (props: `allowInternal`, `status`, `onSubmit`)
- `TicketResolutionBox`

Learner (`components/Pages/Help/`):
- `MyTicketsList`, `TicketCard`, `LearnerTicketDetail`, `RaiseTicketForm`

Staff (`components/Dashboard/Pages/Support/`):
- `SupportQueueFilters`, `SupportQueueTable`, `StaffTicketDetail`,
  `TriageBar`, `ResolveTicketDialog`, `CloseTicketDialog`

## 7. Error handling
- Every mutation shows a toast on failure with the backend's message
  (`errorHandling` already normalises FastAPI `detail`).
- 409 on reply: toast with the backend text, then refetch the ticket so the UI
  shows the closed state.
- 403 on the staff queue: the access message from section 4 (no toast).
- 404 on a `?ticket=` uuid: inline "Ticket not found" in the detail pane and the
  query param is cleared.
- Network failure on queries: React Query's default retry, then an inline
  "Couldn't load tickets. Retry" with a button.
- Buttons are disabled while their request is in flight to prevent double
  submits.

## 8. Testing
- **Unit (bun test, `apps/web/tests/*.test.mjs`):**
  - `tickets-filters.test.mjs`: round-trip and junk handling for
    the filter helpers.
  - `tickets-validation.test.mjs`: boundary lengths for subject/description.
  - `tickets-labels.test.mjs`: every enum value maps to a label and colour.
  - `request-body-patch.test.mjs`: `RequestBodyWithAuthHeader('PATCH', data)`
    includes the JSON body; GET still has none.
- **Type check / lint:** the repo's existing `tsc` and lint scripts pass.
- **Manual end-to-end** (learner + admin accounts, same org): the Postman flow
  from section 1, done entirely in the UI, plus: filters persist across
  refresh, `?ticket=` deep link works for both roles, mobile layout of
  `/dash/support`, signed-out `/help`.

## 9. Files touched

New:
- `apps/web/app/orgs/[orgslug]/(withmenu)/help/{page.tsx,help.tsx,loading.tsx}`
- `apps/web/app/orgs/[orgslug]/dash/support/{page.tsx,client.tsx,page.search.ts}`
- `apps/web/services/tickets/tickets.ts`
- `apps/web/hooks/queries/useTickets.ts`
- `apps/web/lib/tickets/{labels.ts,filters.ts,validation.ts}`
- `apps/web/components/Objects/Tickets/*`
- `apps/web/components/Pages/Help/*`
- `apps/web/components/Dashboard/Pages/Support/*`
- `apps/web/tests/tickets-*.test.mjs`, `apps/web/tests/request-body-patch.test.mjs`

Modified:
- `apps/web/services/utils/ts/requests.ts` (PATCH body)
- `apps/web/lib/query/keys.ts` (ticket keys)
- `apps/web/components/Objects/Menus/OrgMenu.tsx` (Help icon button)
- `apps/web/components/Security/HeaderProfileBox.tsx` (Help menu item)
- `apps/web/components/Dashboard/Menus/DashLeftMenu.tsx`,
  `DashMobileMenu.tsx` (Support link)
- `apps/web/locales/en.json` (strings)
