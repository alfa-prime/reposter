import assert from "node:assert/strict";
import test from "node:test";

const { generateTemporaryPassword, normalizeRoleCodes, toggleRoleCode } = await import("../src/userAdmin.ts");

test("генерирует временный пароль нужной длины без неоднозначных символов", () => {
  const password = generateTemporaryPassword();

  assert.equal(password.length, 20);
  assert.match(password, /^[A-HJ-NP-Za-km-z2-9!@#$%]+$/);
  assert.doesNotMatch(password, /[0O1Il]/);
});

test("добавляет и удаляет код роли без изменения исходного массива", () => {
  const initial = ["editor"];
  const added = toggleRoleCode(initial, "publisher");
  const removed = toggleRoleCode(added, "editor");

  assert.deepEqual(initial, ["editor"]);
  assert.deepEqual(added, ["editor", "publisher"]);
  assert.deepEqual(removed, ["publisher"]);
});

test("делает роль администратора исключительной", () => {
  assert.deepEqual(toggleRoleCode(["editor", "viewer"], "administrator"), ["administrator"]);
  assert.deepEqual(toggleRoleCode(["administrator"], "administrator"), []);
  assert.deepEqual(toggleRoleCode(["administrator"], "editor"), ["editor"]);
  assert.deepEqual(
    normalizeRoleCodes(["administrator", "publisher"]),
    ["administrator"],
  );
});
