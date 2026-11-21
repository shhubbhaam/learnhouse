import { describe, expect, test } from "bun:test";

import {
  MAX_ATTACHMENTS,
  TICKET_IMAGE_MAX_BYTES,
  screenImageFiles,
  ticketAttachmentUrl,
} from "../lib/tickets/attachments.ts";

const file = (name, type, size = 100) => ({ name, type, size });

describe("screenImageFiles", () => {
  test("accepts supported images within the limits", () => {
    const files = [file("a.png", "image/png"), file("b.jpg", "image/jpeg"), file("c.webp", "image/webp"), file("d.gif", "image/gif")];
    expect(screenImageFiles(files, 5)).toEqual({ accepted: files, errors: [] });
  });

  test("rejects unsupported types", () => {
    const r = screenImageFiles([file("a.svg", "image/svg+xml"), file("b.pdf", "application/pdf"), file("c.png", "image/png")], 5);
    expect(r.accepted.map((f) => f.name)).toEqual(["c.png"]);
    expect(r.errors).toEqual(["unsupported_type"]);
  });

  test("rejects files over 10 MB and accepts exactly 10 MB", () => {
    const r = screenImageFiles([file("big.png", "image/png", TICKET_IMAGE_MAX_BYTES + 1), file("ok.png", "image/png", TICKET_IMAGE_MAX_BYTES)], 5);
    expect(r.accepted.map((f) => f.name)).toEqual(["ok.png"]);
    expect(r.errors).toEqual(["too_large"]);
  });

  test("keeps only as many as there are slots left", () => {
    const files = [1, 2, 3].map((i) => file(`${i}.png`, "image/png"));
    const r = screenImageFiles(files, 2);
    expect(r.accepted.map((f) => f.name)).toEqual(["1.png", "2.png"]);
    expect(r.errors).toEqual(["too_many"]);
  });

  test("no slots left accepts nothing", () => {
    expect(screenImageFiles([file("a.png", "image/png")], 0)).toEqual({ accepted: [], errors: ["too_many"] });
  });

  test("reports each kind of problem once", () => {
    const r = screenImageFiles([file("a.svg", "image/svg+xml"), file("b.svg", "image/svg+xml")], 5);
    expect(r.errors).toEqual(["unsupported_type"]);
  });

  test("limit constant matches the backend", () => {
    expect(MAX_ATTACHMENTS).toBe(5);
    expect(TICKET_IMAGE_MAX_BYTES).toBe(10 * 1024 * 1024);
  });
});

describe("ticketAttachmentUrl", () => {
  test("points at the content route without double slashes", () => {
    const url = ticketAttachmentUrl("orgs/o/tickets/t/a.png");
    expect(url.endsWith("content/orgs/o/tickets/t/a.png")).toBe(true);
    expect(url.replace("://", "").includes("//")).toBe(false);
  });
});
