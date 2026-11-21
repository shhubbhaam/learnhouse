import { describe, expect, test } from "bun:test";

import { isValidReply, validateTicketForm } from "../lib/tickets/validation.ts";

const desc = "x".repeat(10);

describe("ticket form validation", () => {
  test("length boundaries", () => {
    expect(validateTicketForm({ subject: "abc", description: desc })).toEqual({});
    expect(validateTicketForm({ subject: "ab", description: desc }).subject).toBe("too_short");
    expect(validateTicketForm({ subject: "a".repeat(200), description: desc })).toEqual({});
    expect(validateTicketForm({ subject: "a".repeat(201), description: desc }).subject).toBe("too_long");
    expect(validateTicketForm({ subject: "abc", description: "x".repeat(9) }).description).toBe("too_short");
    expect(validateTicketForm({ subject: "abc", description: "x".repeat(10000) })).toEqual({});
    expect(validateTicketForm({ subject: "abc", description: "x".repeat(10001) }).description).toBe("too_long");
  });

  test("whitespace is trimmed before measuring", () => {
    expect(validateTicketForm({ subject: "     ", description: desc }).subject).toBe("too_short");
    expect(validateTicketForm({ subject: "  ab  ", description: desc }).subject).toBe("too_short");
    expect(validateTicketForm({ subject: "abc", description: `   ${"x".repeat(9)}   ` }).description).toBe("too_short");
  });

  test("replies", () => {
    expect(isValidReply("   ")).toBe(false);
    expect(isValidReply("ok")).toBe(true);
    expect(isValidReply("x".repeat(10000))).toBe(true);
    expect(isValidReply("x".repeat(10001))).toBe(false);
  });
});
