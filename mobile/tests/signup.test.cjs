const { test } = require("node:test");
const assert = require("node:assert/strict");
const {
  formatBirthDate,
  parseBirthDate,
  validateSignup,
} = require("../src/lib/signup.ts");

const today = new Date(2026, 9, 14);
const valid = {
  name: " Ana ",
  email: " ana@example.com ",
  password: "senha-segura",
  birthDate: "",
};

test("normalizes name/email and allows signup without a birthday", () => {
  assert.deepEqual(validateSignup(valid, today), {
    ok: true,
    name: "Ana",
    email: "ana@example.com",
    birthDate: undefined,
  });
});
test("a single name is accepted; missing or overlong names are not", () => {
  for (const name of ["", " ", "A", "x".repeat(121)]) {
    assert.equal(validateSignup({ ...valid, name }, today).field, "name");
  }
});
test("invalid emails and short/blank passwords are rejected", () => {
  for (const email of ["ana", "ana@", "ana @example.com"]) {
    assert.equal(validateSignup({ ...valid, email }, today).field, "email");
  }
  for (const password of ["", "12345", "      "]) {
    assert.equal(
      validateSignup({ ...valid, password }, today).field,
      "password",
    );
  }
});
test("birthday mask supports partial input and pasted digits", () => {
  for (const [input, expected] of [
    ["1", "1"],
    ["14", "14"],
    ["141", "14/1"],
    ["1410", "14/10"],
    ["14102003", "14/10/2003"],
    ["14/10/2003", "14/10/2003"],
    ["14/", "14"],
  ]) {
    assert.equal(formatBirthDate(input), expected);
  }
});
test("calendar dates and leap years are checked without timezone shifts", () => {
  assert.equal(parseBirthDate("29/02/2000", today), "2000-02-29");
  assert.equal(parseBirthDate("14/10/2026", today), "2026-10-14");
  for (const date of [
    "29/02/2001",
    "31/04/2003",
    "00/10/2003",
    "14/13/2003",
    "14/10/1899",
    "15/10/2026",
    "14/10/20",
  ]) {
    assert.equal(parseBirthDate(date, today), null);
  }
});
test("an optional birthday must still be valid when filled", () => {
  assert.equal(
    validateSignup({ ...valid, birthDate: "31/04/2003" }, today).field,
    "birthDate",
  );
  assert.equal(
    validateSignup({ ...valid, birthDate: "14/10/2003" }, today).birthDate,
    "2003-10-14",
  );
});
