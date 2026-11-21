import { describe, expect, test } from "bun:test";

import { TICKET_CATEGORIES, TICKET_PRIORITIES, TICKET_STATUSES } from "../lib/tickets/types.ts";
import { categoryLabelKey, priorityMeta, statusMeta } from "../lib/tickets/labels.ts";

describe("ticket labels", () => {
  test("every enum value has a label and a class", () => {
    for (const s of TICKET_STATUSES) {
      expect(statusMeta(s).labelKey).toBe(`tickets.status.${s}`);
      expect(statusMeta(s).className.length).toBeGreaterThan(0);
    }
    for (const p of TICKET_PRIORITIES) {
      expect(priorityMeta(p).labelKey).toBe(`tickets.priority.${p}`);
      expect(priorityMeta(p).className.length).toBeGreaterThan(0);
    }
    for (const c of TICKET_CATEGORIES) expect(categoryLabelKey(c)).toBe(`tickets.category.${c}`);
  });

  test("unknown values fall back instead of throwing", () => {
    expect(statusMeta("ESCALATED").labelKey).toBe("tickets.status.unknown");
    expect(priorityMeta(undefined).labelKey).toBe("tickets.priority.unknown");
    expect(categoryLabelKey("NEW_THING")).toBe("tickets.category.OTHER");
  });

  test("statuses read differently at a glance", () => {
    const classes = TICKET_STATUSES.map((s) => statusMeta(s).className);
    expect(new Set(classes).size).toBe(TICKET_STATUSES.length);
  });
});
