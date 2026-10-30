# Help & Support Ticket Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Learners raise and follow support tickets at `/help`; org admins/maintainers triage and resolve them at `/dash/support`.

**Architecture:** Thin typed service (`services/tickets`) over the finished `/api/v1/tickets` API, React Query hooks for reads, plain service calls + cache invalidation for writes. Pure logic (labels, URL filters, form validation) lives in `lib/tickets/` and is unit-tested with `bun test`; UI is split into shared ticket components, learner components and staff components.

**Tech Stack:** Next.js App Router, React, TypeScript, @tanstack/react-query, react-i18next, react-hot-toast, Tailwind, `components/ui/*` (Radix), `@phosphor-icons/react` + `lucide-react`, bun test. Backend: FastAPI + SQLModel (one small fix in Task 1).

**Spec:** `docs/superpowers/specs/2026-10-30-help-support-frontend-design.md`

## Global Constraints

- Commit steps run only after the user has said to commit; otherwise treat them as checkpoints.
- All user-facing text goes through `t()`; keys live in `apps/web/locales/en.json` (Task 5). No hard-coded English in components.
- Validation limits: subject 3–200, description 10–10,000, message 1–10,000 characters, measured **after trimming**.
- Ticket enums are exactly: status `OPEN | IN_PROGRESS | RESOLVED | CLOSED`; priority `LOW | MEDIUM | HIGH | URGENT`; category `TECHNICAL | COURSE_CONTENT | BILLING | ACCOUNT | OTHER`.
- Queue page size 25; default queue status filter `OPEN`.
- API base comes from `getAPIUrl()` (already ends in `/api/v1/`); every request uses `RequestBodyWithAuthHeader` + `errorHandling` from `services/utils/ts/requests.ts`.
- Learner pages only render ticket UI for signed-in users. Staff UI is shown only when the queue request succeeds (403 → access message).
- Dashboard visual language: `bg-[#f8f8f8]` page, `Breadcrumbs`, `text-3xl font-bold` title, black pill primary buttons (`rounded-lg bg-black ... text-white nice-shadow`), as in `app/orgs/[orgslug]/dash/communities/client.tsx`.
- Web commands run from `apps/web`; API commands from `apps/api`.

## Review Focus

1. **Whitespace-only input** (`"   "` subject, blank reply): must be rejected, not stored as an empty ticket. Today the backend checks length *before* stripping, so `"   "` passes. Pinned in Task 1 (backend) and Task 3 (form validation).
2. **Hand-edited or stale URLs** (`?status=FOO&page=-3&ticket=nonexistent`): page must fall back to defaults and show "Ticket not found" rather than crash. Pinned in Task 3 (`queryToFilters`) and Task 8/9 manual checks.
3. **Unknown enum values** from a future backend (e.g. a new status): badges must render a neutral fallback, not throw. Pinned in Task 3 (`labels`).
4. **Long, unbroken content** (a 2,000-char URL in a message or subject): thread and cards must wrap (`break-words`), not overflow the page. Pinned in Task 6 manual check.
5. **Double clicks / in-flight changes** (clicking Resolve twice, changing status while a reply posts): buttons disabled while their request runs; no duplicate messages. Pinned in Task 6 (`TicketReplyBox` disabled state) and Task 9 manual check.

---

### Task 1: Backend – trim text before validating

**Files:**
- Modify: `apps/api/src/db/tickets/tickets.py` (`SupportTicketCreate`, `SupportTicketUpdate`)
- Modify: `apps/api/src/db/tickets/ticket_messages.py` (`TicketMessageCreate`)
- Test: `apps/api/src/tests/services/test_tickets_service.py`

**Interfaces:** Produces: unchanged schemas, now with `model_config = ConfigDict(str_strip_whitespace=True)` so `min_length` applies to trimmed text.

- [ ] **Step 1: Write the failing tests** (add to `TestCreate` / `TestReplies`)

```python
def test_whitespace_only_subject_rejected(self):
    with pytest.raises(ValidationError):
        SupportTicketCreate(org_id=1, subject="     ", description="A real description here.")

def test_whitespace_only_reply_rejected(self):
    with pytest.raises(ValidationError):
        TicketMessageCreate(content="   ")
```
(`from pydantic import ValidationError`)

- [ ] **Step 2: Run to verify they fail**
Run: `uv run pytest src/tests/services/test_tickets_service.py -q -k whitespace`
Expected: 2 failed (DID NOT RAISE).

- [ ] **Step 3: Add `model_config = ConfigDict(str_strip_whitespace=True)`** (`from pydantic import ConfigDict`) to `SupportTicketCreate`, `SupportTicketUpdate`, `TicketMessageCreate`.

- [ ] **Step 4: Run the full ticket tests**
Run: `uv run pytest src/tests/services/test_tickets_service.py src/tests/routers/test_tickets_router.py src/tests/test_root_router.py -q`
Expected: all pass.

- [ ] **Step 5: Commit** `fix(api): trim ticket text before length validation`

---

### Task 2: Shared request helper sends PATCH bodies

**Files:**
- Modify: `apps/web/services/utils/ts/requests.ts` (`RequestBodyWithAuthHeader`, the `body:` line)
- Test: `apps/web/tests/request-body-patch.test.mjs`

**Interfaces:** Produces: `RequestBodyWithAuthHeader('PATCH', data, next, token)` returns `body: JSON.stringify(data)`.

- [ ] **Step 1: Write the failing test**

```js
import { describe, expect, test } from "bun:test";
import { RequestBodyWithAuthHeader } from "../services/utils/ts/requests.ts";

describe("RequestBodyWithAuthHeader", () => {
  test("PATCH sends the JSON body", () => {
    const init = RequestBodyWithAuthHeader("PATCH", { status: "RESOLVED" }, null, "tok");
    expect(init.body).toBe(JSON.stringify({ status: "RESOLVED" }));
    expect(init.headers.get("Authorization")).toBe("Bearer tok");
  });
  test("GET still sends no body", () => {
    expect(RequestBodyWithAuthHeader("GET", { a: 1 }, null).body).toBeNull();
  });
  test("PATCH with null data sends no body", () => {
    expect(RequestBodyWithAuthHeader("PATCH", null, null).body).toBeNull();
  });
});
```

- [ ] **Step 2: Run to verify it fails**
Run: `bun test --isolate tests/request-body-patch.test.mjs`
Expected: "PATCH sends the JSON body" fails (received null).

- [ ] **Step 3: Add `method === 'PATCH'` to the method list in the `body:` expression.**

- [ ] **Step 4: Run** `bun test --isolate tests/request-body-patch.test.mjs` → 3 pass.

- [ ] **Step 5: Commit** `fix(web): send JSON body for PATCH in RequestBodyWithAuthHeader`

---

### Task 3: Pure ticket helpers (`lib/tickets/`)

**Files:**
- Create: `apps/web/lib/tickets/types.ts`, `labels.ts`, `filters.ts`, `validation.ts`
- Test: `apps/web/tests/tickets-labels.test.mjs`, `tickets-filters.test.mjs`, `tickets-validation.test.mjs`

**Interfaces:** Produces:
- `types.ts`: `TicketStatus`, `TicketPriority`, `TicketCategory` (string-literal unions from Global Constraints); `TICKET_STATUSES`, `TICKET_PRIORITIES`, `TICKET_CATEGORIES` (readonly arrays in the order listed); `TicketAuthor { id; user_uuid; username; first_name; last_name; avatar_image? }`; `TicketCourseRef { id; course_uuid; name }`; `SupportTicket` (all fields of backend `SupportTicketRead`: `id, ticket_uuid, org_id, subject, description, category, priority, status, resolution_note: string|null, user_id, course_id: number|null, assigned_to: number|null, creation_date, update_date, author: TicketAuthor|null, assignee: TicketAuthor|null, course: TicketCourseRef|null, message_count`); `TicketMessage { id, message_uuid, ticket_id, author_id, content, is_staff, is_internal, creation_date, author: TicketAuthor|null }`; `SupportTicketDetail = SupportTicket & { messages: TicketMessage[] }`; `SupportTicketPage { items; total; page; limit }`; `SupportTicketCreate { org_id; subject; description; category; course_id?: number|null }`; `SupportTicketUpdate { status?; priority?; assigned_to?: number|null; resolution_note?: string|null }`; `TicketQueueFilters { status: TicketStatus|'ALL'; priority: TicketPriority|'ALL'; category: TicketCategory|'ALL'; mine: boolean; page: number }`.
- `labels.ts`: `statusMeta(s: string): { labelKey: string; className: string }`, `priorityMeta(p: string)`, `categoryLabelKey(c: string): string`. Label keys: `tickets.status.<value>`, `tickets.priority.<value>`, `tickets.category.<value>`; unknown → `tickets.status.unknown` / `tickets.priority.unknown` / `tickets.category.OTHER` with gray class. Colours (Tailwind bg/text pairs): OPEN blue, IN_PROGRESS amber, RESOLVED green, CLOSED gray; URGENT red, HIGH orange, MEDIUM gray, LOW slate.
- `filters.ts`: `DEFAULT_FILTERS: TicketQueueFilters = { status: 'OPEN', priority: 'ALL', category: 'ALL', mine: false, page: 1 }`; `QUEUE_PAGE_SIZE = 25`; `queryToFilters(params: URLSearchParams): TicketQueueFilters`; `filtersToSearchParams(f): URLSearchParams` (URL of the dash page: only non-default values, keys `status, priority, category, mine=1, page`); `filtersToApiQuery(f, currentUserId: number): string` (API query string: omits `ALL`, `mine` → `assigned_to=<id>`, always `page` and `limit=25`).
- `validation.ts`: `validateTicketForm(v: { subject: string; description: string }): { subject?: 'too_short'|'too_long'; description?: 'too_short'|'too_long' }`; `isValidReply(content: string): boolean`. Lengths per Global Constraints, measured on `.trim()`.

- [ ] **Step 1: Write the failing tests**

`tickets-labels.test.mjs`:
```js
test("every enum value has a label and class", () => {
  for (const s of TICKET_STATUSES) expect(statusMeta(s).labelKey).toBe(`tickets.status.${s}`);
  for (const p of TICKET_PRIORITIES) expect(priorityMeta(p).labelKey).toBe(`tickets.priority.${p}`);
  for (const c of TICKET_CATEGORIES) expect(categoryLabelKey(c)).toBe(`tickets.category.${c}`);
});
test("unknown values fall back instead of throwing", () => {
  expect(statusMeta("ESCALATED").labelKey).toBe("tickets.status.unknown");
  expect(priorityMeta(undefined).labelKey).toBe("tickets.priority.unknown");
  expect(categoryLabelKey("NEW_THING")).toBe("tickets.category.OTHER");
});
```

`tickets-filters.test.mjs`:
```js
test("empty params give defaults", () => {
  expect(queryToFilters(new URLSearchParams(""))).toEqual(DEFAULT_FILTERS);
});
test("junk params fall back per field", () => {
  const f = queryToFilters(new URLSearchParams("status=FOO&priority=HIGH&page=-3&mine=yes"));
  expect(f).toEqual({ ...DEFAULT_FILTERS, priority: "HIGH" });
});
test("ALL status is preserved", () => {
  expect(queryToFilters(new URLSearchParams("status=ALL")).status).toBe("ALL");
});
test("round trip through page URL", () => {
  const f = { status: "RESOLVED", priority: "URGENT", category: "BILLING", mine: true, page: 3 };
  expect(queryToFilters(filtersToSearchParams(f))).toEqual(f);
});
test("defaults produce an empty page URL", () => {
  expect(filtersToSearchParams(DEFAULT_FILTERS).toString()).toBe("");
});
test("api query omits ALL and maps mine to assigned_to", () => {
  const q = filtersToApiQuery({ status: "ALL", priority: "HIGH", category: "ALL", mine: true, page: 2 }, 7);
  expect(Object.fromEntries(new URLSearchParams(q))).toEqual({ priority: "HIGH", assigned_to: "7", page: "2", limit: "25" });
});
```

`tickets-validation.test.mjs`:
```js
const desc = "x".repeat(10);
test("boundaries", () => {
  expect(validateTicketForm({ subject: "abc", description: desc })).toEqual({});
  expect(validateTicketForm({ subject: "ab", description: desc }).subject).toBe("too_short");
  expect(validateTicketForm({ subject: "a".repeat(201), description: desc }).subject).toBe("too_long");
  expect(validateTicketForm({ subject: "abc", description: "x".repeat(9) }).description).toBe("too_short");
  expect(validateTicketForm({ subject: "abc", description: "x".repeat(10001) }).description).toBe("too_long");
});
test("whitespace is trimmed before measuring", () => {
  expect(validateTicketForm({ subject: "     ", description: desc }).subject).toBe("too_short");
  expect(validateTicketForm({ subject: "  ab  ", description: desc }).subject).toBe("too_short");
});
test("replies", () => {
  expect(isValidReply("   ")).toBe(false);
  expect(isValidReply("ok")).toBe(true);
  expect(isValidReply("x".repeat(10001))).toBe(false);
});
```

- [ ] **Step 2: Run to verify they fail**
Run: `bun test --isolate tests/tickets-labels.test.mjs tests/tickets-filters.test.mjs tests/tickets-validation.test.mjs`
Expected: fail with module not found.

- [ ] **Step 3: Implement the four files** with the signatures above. `queryToFilters` validates each field independently against the enum arrays (plus `'ALL'`), `page` must be an integer ≥ 1, `mine` is true only for `"1"`.

- [ ] **Step 4: Run the three test files** → all pass.

- [ ] **Step 5: Commit** `feat(web): ticket labels, filter and validation helpers`

---

### Task 4: Ticket service, query keys and hooks

**Files:**
- Create: `apps/web/services/tickets/tickets.ts`
- Create: `apps/web/hooks/queries/useTickets.ts`
- Modify: `apps/web/lib/query/keys.ts` (add `tickets` group before the closing `}` at line 115)
- Test: `apps/web/tests/tickets-service.test.mjs`

**Interfaces:**
- Consumes: types and `filtersToApiQuery` from Task 3; `RequestBodyWithAuthHeader` (Task 2), `errorHandling`.
- Produces (`services/tickets/tickets.ts`, all `async`, all throw on non-2xx via `errorHandling`, `token?: string` last):
  - `getMyTickets(orgId: number, token?): Promise<SupportTicket[]>` → GET `tickets/org/{orgId}/me`
  - `getTicket(uuid: string, token?): Promise<SupportTicketDetail>` → GET `tickets/{uuid}`
  - `getSupportQueue(orgId: number, query: string, token?): Promise<SupportTicketPage>` → GET `tickets/org/{orgId}/admin?{query}`
  - `createTicket(data: SupportTicketCreate, token?): Promise<SupportTicket>` → POST `tickets/`
  - `replyToTicket(uuid: string, data: { content: string; is_internal?: boolean }, token?): Promise<TicketMessage>` → POST `tickets/{uuid}/messages`
  - `updateTicket(uuid: string, data: SupportTicketUpdate, token?): Promise<SupportTicket>` → PATCH `tickets/{uuid}`
  - Re-exports the types from `lib/tickets/types`.
- Produces (`keys.ts`): `tickets: { all: ['tickets'], mine: (orgId: number) => ['tickets','mine',orgId], detail: (uuid: string) => ['tickets','detail',uuid], queue: (orgId: number, query: string) => ['tickets','queue',orgId,query] }`.
- Produces (`useTickets.ts`, modelled on `hooks/queries/useTrail.ts`, `staleTime: 30_000`, token from `useLHSession()`):
  - `useMyTickets(orgId?: number)` (enabled when orgId and token)
  - `useTicket(uuid?: string | null)` (enabled when uuid and token; `retry: false` so a 404 shows immediately)
  - `useSupportQueue(orgId: number | undefined, query: string)` (`retry: false`, so 403 shows the access message)
  - `useInvalidateTickets(): () => Promise<void>`: invalidates `queryKeys.tickets.all` (all ticket queries; simplest correct rule for create/reply/update).

- [ ] **Step 1: Write the failing test** (mocks `globalThis.fetch`; restores it in `afterEach`)

```js
test("updateTicket PATCHes the uuid with a JSON body", async () => {
  let call;
  globalThis.fetch = async (url, init) => { call = { url, init }; return new Response(JSON.stringify({ ticket_uuid: "ticket_1" }), { status: 200 }); };
  await updateTicket("ticket_1", { status: "RESOLVED", resolution_note: "done" }, "tok");
  expect(call.url.endsWith("tickets/ticket_1")).toBe(true);
  expect(call.init.method).toBe("PATCH");
  expect(JSON.parse(call.init.body)).toEqual({ status: "RESOLVED", resolution_note: "done" });
});
test("getSupportQueue appends the query", async () => {
  let url;
  globalThis.fetch = async (u) => { url = u; return new Response(JSON.stringify({ items: [], total: 0, page: 1, limit: 25 })); };
  await getSupportQueue(1, "status=OPEN&page=1&limit=25", "tok");
  expect(url.endsWith("tickets/org/1/admin?status=OPEN&page=1&limit=25")).toBe(true);
});
test("errors surface the backend detail", async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: "This ticket is closed." }), { status: 409 });
  await expect(replyToTicket("ticket_1", { content: "hi" }, "tok")).rejects.toThrow("This ticket is closed.");
});
```

- [ ] **Step 2: Run** `bun test --isolate tests/tickets-service.test.mjs` → fails (module not found).

- [ ] **Step 3: Implement the service, keys and hooks** per Interfaces. Check what `errorHandling` throws (read it in `requests.ts`) and keep the third test's assertion aligned with its message format.

- [ ] **Step 4: Run** `bun test --isolate tests/tickets-service.test.mjs` → 3 pass.

- [ ] **Step 5: Commit** `feat(web): tickets service, query keys and hooks`

---

### Task 5: Locale strings

**Files:** Modify: `apps/web/locales/en.json` (add three top-level groups; keep existing JSON formatting)

**Interfaces:** Produces these keys (values are the English copy):
- `tickets.status.{OPEN: "Open", IN_PROGRESS: "In progress", RESOLVED: "Resolved", CLOSED: "Closed", unknown: "Unknown"}`
- `tickets.priority.{LOW: "Low", MEDIUM: "Medium", HIGH: "High", URGENT: "Urgent", unknown: "Unknown"}`
- `tickets.category.{TECHNICAL: "Technical", COURSE_CONTENT: "Course content", BILLING: "Billing", ACCOUNT: "Account", OTHER: "Other"}`
- `tickets.thread.{support_team: "Support team", internal: "Internal", you: "You"}`
- `tickets.reply.{placeholder: "Write a reply…", send: "Send", internal_toggle: "Internal note", internal_send: "Add internal note", reopen_hint: "Still having trouble? Replying will reopen this ticket.", closed: "This ticket is closed. Raise a new ticket if you still need help.", sent: "Reply sent"}`
- `tickets.resolution: "Resolution"`, `tickets.not_found: "Ticket not found"`, `tickets.load_error: "Couldn't load tickets."`, `tickets.retry: "Retry"`, `tickets.messages_count: "{{count}} messages"`, `tickets.updated: "Updated {{time}}"`
- `help.{title: "Help & Support", description: "Get help with your account and courses", sign_in: "Sign in to contact support.", tab_my_tickets: "My tickets", tab_raise: "Raise a ticket", back: "Back to my tickets", empty: "You haven't raised any tickets yet", raise_new: "Raise a new ticket"}`
- `help.form.{subject: "Subject", subject_placeholder: "Short summary of the problem", category: "Category", course: "Related course", course_none: "None", description: "Description", description_placeholder: "What happened? What did you expect? Steps to reproduce help a lot.", submit: "Submit ticket", submitted: "Ticket submitted", errors: {too_short: "Too short", too_long: "Too long"}}`
- `dashboard.support.{title: "Support", access_denied: "Support tickets are available to organization admins and maintainers.", filter_status: "Status", filter_priority: "Priority", filter_category: "Category", all: "All", assigned_to_me: "Assigned to me", unassigned: "Unassigned", empty: "No tickets match these filters", showing: "Showing {{from}}–{{to}} of {{total}}", previous: "Previous", next: "Next", select_ticket: "Select a ticket to see details", learner: "Learner", assignee: "Assignee", assign_me: "Assign to me", unassign: "Unassign", resolve: "Resolve", resolve_title: "Resolve ticket", resolve_note: "Resolution note", resolve_note_hint: "The learner sees this on their ticket.", resolve_confirm: "Mark as resolved", close: "Close ticket", close_confirm: "Close this ticket? Nobody will be able to reply.", reopen: "Reopen", updated: "Ticket updated", cancel: "Cancel"}`
- `dashboard.search.entries.support.{description: "Triage and resolve learner support tickets", keywords: "support, tickets, help, helpdesk, issues"}`

- [ ] **Step 1: Add the keys.** Before adding, check `en.json` for existing top-level `help`, `tickets`, `dashboard.support`; if any exists, nest under it without overwriting.
- [ ] **Step 2: Verify JSON and key presence**
Run: `node -e "const j=require('./locales/en.json');for(const k of ['tickets.status.OPEN','help.form.submit','dashboard.support.resolve','dashboard.search.entries.support.description'])if(k.split('.').reduce((o,p)=>o?.[p],j)===undefined)throw k;console.log('ok')"`
Expected: `ok`
- [ ] **Step 3: Commit** `feat(web): help & support strings`

---

### Task 6: Shared ticket components

**Files:** Create in `apps/web/components/Objects/Tickets/`:
`TicketStatusBadge.tsx`, `TicketPriorityBadge.tsx`, `TicketResolutionBox.tsx`, `TicketThread.tsx`, `TicketReplyBox.tsx`

**Interfaces:**
- Consumes: `statusMeta`, `priorityMeta`, `isValidReply` (Task 3); types (Task 3); `formatRelative` from `lib/format.ts`; `UserAvatar` component used by `components/Objects/Communities/CommentCard.tsx` (reuse the same import).
- Produces:
  - `TicketStatusBadge({ status }: { status: string })`, `TicketPriorityBadge({ priority }: { priority: string })`: pill with `t(meta.labelKey)` and `meta.className`.
  - `TicketResolutionBox({ note }: { note: string | null })`: renders nothing when `!note`; green box, heading `tickets.resolution`, note with `whitespace-pre-wrap break-words`.
  - `TicketThread({ messages, viewerUserId }: { messages: TicketMessage[]; viewerUserId?: number })`: oldest first as given; each message shows avatar, name (or `tickets.thread.you` when `author_id === viewerUserId`), `formatRelative(creation_date)`, content `whitespace-pre-wrap break-words`. `is_staff` → tinted background + `tickets.thread.support_team` label; `is_internal` → amber background + `tickets.thread.internal` label (internal wins).
  - `TicketReplyBox({ status, allowInternal, onSubmit }: { status: TicketStatus; allowInternal: boolean; onSubmit: (content: string, isInternal: boolean) => Promise<void> })`: textarea + send button; disabled while `onSubmit` is pending or `!isValidReply(content)`; clears on success, keeps text on error. `CLOSED` → renders `tickets.reply.closed` text instead of the form. `RESOLVED` → shows `tickets.reply.reopen_hint`. With `allowInternal`, a switch (`components/ui/switch`) toggles internal mode: amber border and `tickets.reply.internal_send` button label.

- [ ] **Step 1: Implement the five components** per Interfaces using Tailwind classes consistent with `components/Objects/Communities/CommentCard.tsx`.
- [ ] **Step 2: Type-check the new files**
Run: `npx tsc --noEmit -p . 2>&1 | grep -i "Objects/Tickets"`
Expected: no output.
- [ ] **Step 3: Commit** `feat(web): shared ticket components`

(These components are exercised through the pages in Tasks 7–8 and the manual pass in Task 9; the logic they depend on is unit-tested in Task 3.)

---

### Task 7: Learner `/help` page

**Files:**
- Create: `apps/web/app/orgs/[orgslug]/(withmenu)/help/page.tsx`, `help.tsx`, `loading.tsx`
- Create: `apps/web/components/Pages/Help/MyTicketsList.tsx`, `TicketCard.tsx`, `LearnerTicketDetail.tsx`, `RaiseTicketForm.tsx`
- Modify: `apps/web/components/Objects/Menus/OrgMenu.tsx` (Help icon next to the Trail icon, ~line 183)
- Modify: `apps/web/components/Security/HeaderProfileBox.tsx` (menu item after Purchases, ~line 256)

**Interfaces:**
- Consumes: hooks + `useInvalidateTickets` (Task 4); `createTicket`, `replyToTicket` (Task 4); `validateTicketForm`, `TICKET_CATEGORIES`, `categoryLabelKey` (Task 3); shared components (Task 6); `useCourses(orgslug)` from `hooks/queries/useCourses.ts`; `useOrg`, `useLHSession`; `GeneralWrapperStyled`, `TypeOfContentTitle` (as in `trail/trail.tsx`); `components/ui/tabs`, `select`, `input`, `textarea`, `label`; `toast` from `react-hot-toast`.
- Produces: route `/help` (`?tab=raise|mine`, `?ticket={uuid}`).
  - `page.tsx`: `generateMetadata` → title `"Help & Support | " + org.name`; renders `<Help orgslug={orgslug} />` (copy the shape of `trail/page.tsx`, `export const dynamic = 'force-dynamic'`).
  - `help.tsx` (client): if no session → `help.sign_in` with a link to the org login page used elsewhere in `OrgMenu.tsx`. Else tabs `mine` (default) / `raise`, synced to `?tab=`. When `?ticket=` is set on the `mine` tab, render `LearnerTicketDetail` instead of the list.
  - `MyTicketsList({ orgId, onOpen(uuid), onRaise() })`: `useMyTickets`; loading skeleton; error → `tickets.load_error` + retry (`refetch`); empty → `help.empty` + `help.raise_new` button.
  - `TicketCard({ ticket, onClick })`: subject (truncate to 2 lines, `break-words`), status badge, category label, course name, `tickets.updated` with `formatRelative(update_date)`, `tickets.messages_count`.
  - `LearnerTicketDetail({ uuid, onBack })`: `useTicket(uuid)`; 404 → `tickets.not_found` + back. Shows header, description, `TicketResolutionBox`, `TicketThread` (`viewerUserId` = session user id), `TicketReplyBox` (`allowInternal={false}`); reply → `replyToTicket` → toast `tickets.reply.sent` → `invalidate()`; error toast with `error.message`, and on a closed-ticket error also `invalidate()` so the closed state appears.
  - `RaiseTicketForm({ orgId, orgslug, onCreated(uuid) })`: fields per spec §3.3, category default `TECHNICAL`, course select from `useCourses(orgslug)` with `help.form.course_none` (→ `course_id: null`); per-field errors from `validateTicketForm` shown after first blur/submit; submit disabled while invalid or pending; success → toast `help.form.submitted`, `invalidate()`, reset, `onCreated(ticket.ticket_uuid)` (switches to `mine` with `?ticket=`).
  - Nav: `Lifebuoy` (`@phosphor-icons/react`) icon link to `getUriWithOrg(orgslug, '/help')` with tooltip `help.title`, wrapped in `AuthenticatedClientElement checkMethod="authentication"`, markup copied from the Trail button. Profile dropdown item `Lifebuoy` + `help.title` linking to `getUriWithOrg(org?.slug, '/help')`.

- [ ] **Step 1: Implement route files and the four components** per Interfaces.
- [ ] **Step 2: Add the two navigation entries.**
- [ ] **Step 3: Type-check**
Run: `npx tsc --noEmit -p . 2>&1 | grep -iE "help/|Pages/Help|OrgMenu|HeaderProfileBox"`
Expected: no output.
- [ ] **Step 4: Smoke-check in the browser** (`npx learnhouse dev` from repo root): as a learner, open `/help`, raise a ticket, confirm it opens with status Open; refresh keeps `?ticket=`; signed out shows the sign-in message.
- [ ] **Step 5: Commit** `feat(web): learner help & support page`

---

### Task 8: Staff `/dash/support` page

**Files:**
- Create: `apps/web/app/orgs/[orgslug]/dash/support/page.tsx`, `client.tsx`, `page.search.ts`
- Create: `apps/web/components/Dashboard/Pages/Support/SupportQueueFilters.tsx`, `SupportQueueTable.tsx`, `StaffTicketDetail.tsx`, `TriageBar.tsx`, `ResolveTicketDialog.tsx`, `CloseTicketDialog.tsx`
- Modify: `apps/web/components/Dashboard/Menus/DashLeftMenu.tsx` (link after Communities, ~line 492), `DashMobileMenu.tsx` (same position)

**Interfaces:**
- Consumes: `useSupportQueue`, `useTicket`, `useInvalidateTickets`, `replyToTicket`, `updateTicket` (Task 4); `queryToFilters`, `filtersToSearchParams`, `filtersToApiQuery`, `QUEUE_PAGE_SIZE`, enum arrays, label helpers (Task 3); shared components (Task 6); `Breadcrumbs`; `components/ui/select`, `dialog`, `switch`, `textarea`; `toast`.
- Produces: route `/dash/support` with URL state `status, priority, category, mine, page, ticket`.
  - `page.tsx`: as `dash/communities/page.tsx` minus data fetching: `generateMetadata` → `"Support | " + org.name`, `robots: { index: false, follow: false }`; renders `<SupportDashClient orgId={org.id} orgslug={orgslug} />`.
  - `page.search.ts`: `searchMeta = { id: 'dash.support', titleKey: 'dashboard.support.title', descriptionKey: 'dashboard.search.entries.support.description', keywordsKey: 'dashboard.search.entries.support.keywords', icon: Lifebuoy, href: '/dash/support', group: 'navigation' }` (no `featureKey`).
  - `client.tsx`: reads filters with `queryToFilters(useSearchParams())`; changing a filter calls `router.replace` with `filtersToSearchParams({...f, page: 1})` (keeps `ticket`); queries `useSupportQueue(orgId, filtersToApiQuery(f, sessionUserId))`. Error whose message indicates 403 (check status via a `status` property if `errorHandling` provides one, else match the backend detail "Only organization admins and maintainers") → render only `dashboard.support.access_denied`. Layout per Global Constraints; `lg:grid lg:grid-cols-5` with queue `col-span-2`, detail `col-span-3`; below `lg` show detail instead of queue when `ticket` is set, with a back link.
  - `SupportQueueFilters({ filters, onChange(next) })`: three selects (status, priority, category, each with `ALL` → `dashboard.support.all`) and an "Assigned to me" switch.
  - `SupportQueueTable({ page: SupportTicketPage, selectedUuid, onSelect(uuid), onPage(n) })`: rows per spec §4.1, selected row highlighted, footer `dashboard.support.showing` + Previous/Next (disabled at bounds, using `total` and `QUEUE_PAGE_SIZE`), empty → `dashboard.support.empty`.
  - `StaffTicketDetail({ uuid, orgId, currentUserId })`: `useTicket(uuid)`; 404 → `tickets.not_found` and clear `ticket` from URL. Header (learner avatar/name/username, course, created), `TriageBar`, description, `TicketResolutionBox`, `TicketThread`, `TicketReplyBox allowInternal`; reply → `replyToTicket(uuid, { content, is_internal })` → toast → `invalidate()`.
  - `TriageBar({ ticket, currentUserId, onUpdate(data: SupportTicketUpdate): Promise<void> })`: status select, priority select, "Assign to me" (sends `assigned_to: currentUserId`) or "Unassign" when assigned to the current user (sends `assigned_to: null`), shows assignee name otherwise; **Resolve** (black pill) opens `ResolveTicketDialog`; **Close ticket** opens `CloseTicketDialog`; on `CLOSED` shows **Reopen** (`{ status: 'OPEN' }`). All controls disabled while an update is pending. `onUpdate` in the parent calls `updateTicket` → toast `dashboard.support.updated` → `invalidate()`; errors toast `error.message`.
  - `ResolveTicketDialog({ open, initialNote, onConfirm(note), onOpenChange })`: textarea prefilled with `initialNote ?? ''`, hint `resolve_note_hint`, confirm disabled while note is blank (trimmed) or pending; confirm → `onUpdate({ status: 'RESOLVED', resolution_note: note })`.
  - `CloseTicketDialog({ open, onConfirm(), onOpenChange })`: text `close_confirm`, confirm → `onUpdate({ status: 'CLOSED' })`.
  - Menus: `href="/dash/support"`, label `dashboard.support.title`, icon `Lifebuoy`, active via `isActivePath('/dash/support')`, matching the Communities entry's markup; not feature-gated.

- [ ] **Step 1: Implement route files and the six components** per Interfaces.
- [ ] **Step 2: Add the menu entries.**
- [ ] **Step 3: Type-check**
Run: `npx tsc --noEmit -p . 2>&1 | grep -iE "dash/support|Pages/Support|DashLeftMenu|DashMobileMenu"`
Expected: no output.
- [ ] **Step 4: Smoke-check in the browser** as an admin: queue shows the ticket from Task 7; filters change the URL and survive refresh; Resolve with a note updates the row badge.
- [ ] **Step 5: Commit** `feat(web): staff support queue and triage`

---

### Task 9: Full verification

**Files:** none (fix-ups go back into the owning task's files)

- [ ] **Step 1: Unit tests** – `bun test --isolate tests` (from `apps/web`) → all pass, including the 5 new ticket test files.
- [ ] **Step 2: API tests** – `uv run pytest src/tests/services/test_tickets_service.py src/tests/routers/test_tickets_router.py src/tests/test_root_router.py -q` (from `apps/api`) → all pass.
- [ ] **Step 3: Type-check and lint** – `npx tsc --noEmit -p .` shows no errors in files listed in this plan; `npx eslint <the new/modified web files>` shows no errors.
- [ ] **Step 4: Manual end-to-end** with a learner and an admin in the same org, all in the UI:
  1. Learner raises a ticket (category Technical, with a course) → appears Open/Medium in My tickets.
  2. Admin sees it in the Open queue; assigns to self; sets priority High.
  3. Admin replies, then adds an internal note (amber, "Internal").
  4. Learner refreshes the ticket: sees the reply labelled "Support team", **not** the internal note.
  5. Admin resolves with a note → learner sees the green Resolution box and the reopen hint.
  6. Learner replies → ticket shows Open again in both views.
  7. Admin closes → learner's reply box is replaced with the closed message; admin sees Reopen.
  8. Review Focus checks: subject of only spaces is blocked; `/dash/support?status=FOO&page=-3` loads with defaults; `?ticket=ticket_nope` shows "Ticket not found"; a 2,000-char unbroken string in a reply wraps; double-clicking Send posts one message.
  9. Non-admin with dashboard access opening `/dash/support` sees the access message; signed-out `/help` shows the sign-in message; `/dash/support` at mobile width shows queue then detail with a back link.
- [ ] **Step 5: Commit** any fix-ups `fix(web): help & support review fixes`
