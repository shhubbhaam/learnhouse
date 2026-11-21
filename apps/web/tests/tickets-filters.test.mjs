import { describe, expect, test } from "bun:test";

import {
  DEFAULT_FILTERS,
  filtersToApiQuery,
  filtersToSearchParams,
  queryToFilters,
} from "../lib/tickets/filters.ts";

describe("support queue filters", () => {
  test("empty params give defaults", () => {
    expect(queryToFilters(new URLSearchParams(""))).toEqual(DEFAULT_FILTERS);
  });

  test("junk params fall back per field", () => {
    const f = queryToFilters(new URLSearchParams("status=FOO&priority=HIGH&page=-3&mine=yes"));
    expect(f).toEqual({ ...DEFAULT_FILTERS, priority: "HIGH" });
  });

  test("non-integer page falls back to 1", () => {
    expect(queryToFilters(new URLSearchParams("page=2.5")).page).toBe(1);
    expect(queryToFilters(new URLSearchParams("page=abc")).page).toBe(1);
  });

  test("ALL status is preserved", () => {
    expect(queryToFilters(new URLSearchParams("status=ALL")).status).toBe("ALL");
  });

  test("round trip through the page URL", () => {
    const f = { status: "RESOLVED", priority: "URGENT", category: "BILLING", mine: true, page: 3 };
    expect(queryToFilters(filtersToSearchParams(f))).toEqual(f);
  });

  test("defaults produce an empty page URL", () => {
    expect(filtersToSearchParams(DEFAULT_FILTERS).toString()).toBe("");
  });

  test("api query omits ALL and maps mine to assigned_to", () => {
    const q = filtersToApiQuery({ status: "ALL", priority: "HIGH", category: "ALL", mine: true, page: 2 }, 7);
    expect(Object.fromEntries(new URLSearchParams(q))).toEqual({
      priority: "HIGH",
      assigned_to: "7",
      page: "2",
      limit: "25",
    });
  });

  test("api query for defaults asks for open tickets, first page", () => {
    expect(Object.fromEntries(new URLSearchParams(filtersToApiQuery(DEFAULT_FILTERS, 1)))).toEqual({
      status: "OPEN",
      page: "1",
      limit: "25",
    });
  });
});
