# Ticket Image Attachments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Private image attachments on support tickets and replies (owner + org staff only; internal-note images staff only).

**Architecture:** A `ticketattachment` table records every upload. Files are stored with the existing `upload_file` helper under `orgs/{org}/tickets/{ticket}/[internal/]`. A shared access check (`src/security/ticket_file_access.py`) is called by both content routers. Replies link pending uploads by `attachment_uuids`. The web client loads images with a bearer-token fetch into blob URLs.

**Tech Stack:** FastAPI, SQLModel, Alembic, pytest (API); Next.js, React Query, bun test (web).

**Spec:** `docs/superpowers/specs/2026-10-30-help-support-frontend-design.md` (Addendum A1–A5)

## Global Constraints
- Image types `image/jpeg, image/png, image/gif, image/webp`; max `10 * 1024 * 1024` bytes; max 5 per message and 5 ticket-level; max 20 pending (unsent) uploads per user per ticket.
- Content path: `orgs/{org_uuid}/tickets/{ticket_uuid}/{file_id}`; internal: `orgs/{org_uuid}/tickets/{ticket_uuid}/internal/{file_id}`.
- Staff = org admin/maintainer or superadmin (reuse `_is_staff` from `services/tickets/tickets.py`).
- No commits unless the user asks. New strings go in `en.json` **and** `ar.json` (the Arabic coverage test requires it).

## Review Focus
1. **Leaked link**: a logged-in user from another org (or a learner in the same org) opening a ticket image URL gets 403, never the image. Pinned in Task 2 tests.
2. **Path tricks**: `orgs/<other-org>/tickets/<ticket>/file` with a real ticket from a different org → 403. Pinned in Task 2.
3. **Internal leak**: the ticket owner can't load an internal-note image, and the detail API never lists it to them. Pinned in Tasks 2 and 3.
4. **Attaching someone else's upload** to your reply via its uuid → 400. Pinned in Task 3.
5. **Switching the internal toggle after uploading** would send a public image as internal (or the reverse): the toggle is disabled while images are attached. Pinned in Task 6 manual check.

---

### Task 1: Model + migration
**Files:** Create `apps/api/src/db/tickets/ticket_attachments.py`, `apps/api/migrations/versions/f2a3b4c5d6e7_add_ticket_attachments.py` (down_revision `e1ebd9e62249`). Modify `ticket_messages.py` (`TicketMessageCreate.attachment_uuids: list[str] = Field(default_factory=list, max_length=5)`, `content` default `""`, model validator: content or attachments required; `TicketMessageRead.attachments: list[TicketAttachmentRead] = []`; `SupportTicketDetail.attachments: list[TicketAttachmentRead] = []`).
**Interfaces (produces):** `TicketAttachment` table per spec A3; `TicketAttachmentRead { attachment_uuid, file_path, content_type, size, is_internal }`; constants `TICKET_IMAGE_TYPES`, `TICKET_IMAGE_MAX_BYTES`, `MAX_ATTACHMENTS_PER_MESSAGE = 5`, `MAX_PENDING_PER_USER = 20`.
- [ ] Tests (service file): `TicketMessageCreate(content="")` → ValidationError; `TicketMessageCreate(content="", attachment_uuids=["a"])` OK; 6 uuids → ValidationError.
- [ ] Implement; user runs `uv run pytest src/tests/services/test_tickets_service.py -q` and `uv run alembic upgrade f2a3b4c5d6e7`.

### Task 2: File access rule (both content routers)
**Files:** Create `apps/api/src/security/ticket_file_access.py`; modify `_check_content_access` in `routers/local_content.py` and `routers/content_files.py` (call right after the submission-file check). Test: `apps/api/src/tests/security/test_ticket_file_access.py`.
**Interfaces:** `is_ticket_file(parts: list[str]) -> bool` (`len(parts) >= 5 and parts[0] == 'orgs' and parts[2] == 'tickets'`); `async enforce_ticket_file_access(parts, current_user, db_session) -> None` (raises 401/403, returns on success) per spec A3.
- [ ] Tests (db fixtures, rows inserted directly): owner loads own attached file ✓; owner → internal file 403; owner → pending file uploaded by staff 403; uploader → own pending ✓; staff ✓ for all; other learner same org 403; admin of other org 403; wrong org uuid in path 403; file with no attachment row 403 (staff too); anonymous 401; APITokenUser 403; `is_ticket_file` true/false cases.
- [ ] Implement; wire into both routers.

### Task 3: Upload endpoint + reply linking + read models
**Files:** Create `apps/api/src/services/tickets/attachments.py`; modify `services/tickets/tickets.py` (`add_ticket_message` links attachments; `get_ticket_detail` and `_serialize_message` include attachments; staff-only filtering), `routers/tickets.py` (`POST /{ticket_uuid}/attachments`, multipart: `file: UploadFile`, `is_internal: bool = Form(False)`, `attach_to_ticket: bool = Form(False)`).
**Interfaces:** `async upload_ticket_attachment(db_session, ticket_uuid, file, is_internal, attach_to_ticket, current_user) -> TicketAttachmentRead`; `async attachments_for(db_session, ticket, message_ids, include_internal) -> (ticket_level: list[TicketAttachmentRead], by_message: dict[int, list[TicketAttachmentRead]])`.
Rules: visible-ticket check (404); CLOSED → 409; `is_internal` needs staff (403); `attach_to_ticket` needs owner and not internal (403), and ≤5 attached ticket-level (400); pending per user per ticket ≤20 (400); `upload_file(..., directory=f"tickets/{ticket_uuid}" or ".../internal", type_of_dir="orgs", uuid=org.org_uuid, allowed_types=["image"], filename_prefix="ticket", max_size=TICKET_IMAGE_MAX_BYTES)`.
Reply linking: each uuid must be a row on this ticket, `uploader_id == caller`, `attached is False`, `is_internal == msg.is_internal`; else 400 `"Invalid attachment"`. On success set `attached=True, message_id=message.id`.
- [ ] Tests (patch `src.services.tickets.attachments.upload_file` → returns `"abc_ticket.png"`): owner upload pending ✓; owner `attach_to_ticket` ✓ and appears in `detail.attachments`; learner `is_internal` → 403; other learner → 404; closed → 409; 6th ticket-level → 400; reply links own pending ✓ and it appears in `messages[i].attachments`; reply with someone else's uuid → 400; reply reusing an attached uuid → 400; internal-mismatch → 400; owner's detail view excludes internal-note attachments; staff's includes them; images-only reply (empty content) ✓.
- [ ] Implement.

### Task 4: Web data layer
**Files:** Create `apps/web/lib/tickets/attachments.ts`; modify `lib/tickets/types.ts` (`TicketAttachment`; `attachments` on `TicketMessage` and `SupportTicketDetail`), `services/tickets/tickets.ts` (`uploadTicketAttachment(uuid, file, opts: { isInternal?: boolean; attachToTicket?: boolean }, token)` via `RequestBodyFormWithAuthHeader`, field names `file`, `is_internal`, `attach_to_ticket`; `replyToTicket` data gains `attachment_uuids?: string[]`). Tests: `tests/tickets-attachments.test.mjs`, extend `tests/tickets-service.test.mjs`.
**Interfaces:** `TICKET_IMAGE_TYPES`, `TICKET_IMAGE_MAX_BYTES`, `MAX_ATTACHMENTS = 5`; `screenImageFiles(files: File[], remaining: number): { accepted: File[]; errors: ('unsupported_type'|'too_large'|'too_many')[] }`; `ticketAttachmentUrl(filePath: string): string` (`${getMediaUrl()}content/${filePath}`).
- [ ] Tests: type/size/count screening incl. remaining=0; URL builder; upload sends multipart with the three fields to `tickets/{uuid}/attachments`.
- [ ] Implement.

### Task 5: Image display
**Files:** Create `components/Objects/Tickets/useAuthedImage.ts` (fetch with bearer → blob URL, revoke on unmount; `{ src, error }`), `components/Objects/Tickets/TicketAttachmentGrid.tsx` (`{ attachments: TicketAttachment[] }`: 80px thumbnails, broken-image placeholder on error, click opens LearnHouse `Modal` with the full image). Modify `TicketThread.tsx` (grid under each message), `LearnerTicketDetail.tsx` and `StaffTicketDetail.tsx` (grid under description).
- [ ] bun build check; manual check in Task 7.

### Task 6: Attaching in the UI
**Files:** Modify `TicketReplyBox.tsx` (props add `ticketUuid: string`; image button + hidden `<input type="file" multiple accept=…>`, paste support via `imageFilesFrom`; uploads immediately with `isInternal` = current toggle; previews with remove; internal toggle disabled while any image is attached; send passes `attachment_uuids`; send allowed with images and empty text), `RaiseTicketForm.tsx` (pick up to 5 images locally with previews; after `createTicket`, upload each with `attachToTicket: true`; on any upload failure toast `tickets.attachments.partial_failure` but still open the ticket), parents pass `ticketUuid`. Strings in `en.json` + `ar.json`: `tickets.attachments.{add, remove, uploading, unsupported_type, too_large, too_many, upload_failed, partial_failure, view, image_unavailable}`.
- [ ] bun build check; Arabic key-coverage check passes.

### Task 7: Verification
- [ ] `bun test --isolate tests` (web) all green.
- [ ] `uv run pytest src/tests/services/test_tickets_service.py src/tests/security/test_ticket_file_access.py src/tests/routers/test_tickets_router.py -q` green.
- [ ] `uv run alembic upgrade f2a3b4c5d6e7`.
- [ ] Manual: learner raises ticket with 2 screenshots → visible under description; admin replies with an image and an internal note with an image; learner sees reply image but not internal one; copying an image URL into a different browser (not logged in) → 401; logged in as another learner → 403; pasting a screenshot into the reply box works; internal toggle locked while images are attached.
