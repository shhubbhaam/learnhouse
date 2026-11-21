import { describe, expect, test } from "bun:test";

import { RequestBodyWithAuthHeader } from "../services/utils/ts/requests.ts";

// PATCH carries partial updates (e.g. ticket triage). Before this fix the
// helper dropped PATCH bodies, so the API received an empty update and still
// answered 200.
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
