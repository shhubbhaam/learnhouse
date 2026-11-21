import { afterEach, describe, expect, test } from "bun:test";

import { getSupportQueue, replyToTicket, updateTicket, uploadTicketAttachment } from "../services/tickets/tickets.ts";

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("tickets service", () => {
  test("updateTicket PATCHes the uuid with a JSON body", async () => {
    let call;
    globalThis.fetch = async (url, init) => {
      call = { url, init };
      return json({ ticket_uuid: "ticket_1" });
    };
    await updateTicket("ticket_1", { status: "RESOLVED", resolution_note: "done" }, "tok");
    expect(call.url.endsWith("tickets/ticket_1")).toBe(true);
    expect(call.init.method).toBe("PATCH");
    expect(JSON.parse(call.init.body)).toEqual({ status: "RESOLVED", resolution_note: "done" });
  });

  test("getSupportQueue appends the query", async () => {
    let url;
    globalThis.fetch = async (u) => {
      url = u;
      return json({ items: [], total: 0, page: 1, limit: 25 });
    };
    await getSupportQueue(1, "status=OPEN&page=1&limit=25", "tok");
    expect(url.endsWith("tickets/org/1/admin?status=OPEN&page=1&limit=25")).toBe(true);
  });

  test("errors surface the backend detail and status", async () => {
    globalThis.fetch = async () => json({ detail: "This ticket is closed." }, 409);
    const err = await replyToTicket("ticket_1", { content: "hi" }, "tok").catch((e) => e);
    expect(err.message).toBe("This ticket is closed.");
    expect(err.status).toBe(409);
  });

  test("uploadTicketAttachment posts multipart with the three fields", async () => {
    let call;
    globalThis.fetch = async (url, init) => {
      call = { url, init };
      return json({ attachment_uuid: "ticketatt_1", file_path: "orgs/o/tickets/t/a.png", content_type: "image/png", size: 1, is_internal: true });
    };
    const f = new File(["x"], "a.png", { type: "image/png" });
    const res = await uploadTicketAttachment("ticket_1", f, { isInternal: true }, "tok");
    expect(res.attachment_uuid).toBe("ticketatt_1");
    expect(call.url.endsWith("tickets/ticket_1/attachments")).toBe(true);
    expect(call.init.method).toBe("POST");
    expect(call.init.body.get("file").name).toBe("a.png");
    expect(call.init.body.get("is_internal")).toBe("true");
    expect(call.init.body.get("attach_to_ticket")).toBe("false");
  });

  test("replyToTicket sends attachment uuids", async () => {
    let body;
    globalThis.fetch = async (_u, init) => {
      body = JSON.parse(init.body);
      return json({});
    };
    await replyToTicket("ticket_1", { content: "", attachment_uuids: ["ticketatt_1"] }, "tok");
    expect(body).toEqual({ content: "", attachment_uuids: ["ticketatt_1"] });
  });
});
