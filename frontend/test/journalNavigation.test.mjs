import assert from "node:assert/strict";
import test from "node:test";
import { firstJournalPage, navigationForKey, nextJournalPage, previousJournalPage } from "../src/journalNavigation.ts";

test("changing filters or page size starts from the beginning", () => {
  const first = firstJournalPage("target9:limit20");
  const next = nextJournalPage(first, "boundary1");
  assert.equal(navigationForKey(next, "target9:limit20"), next);
  assert.deepEqual(navigationForKey(next, "target10:limit20"), firstJournalPage("target10:limit20"));
  assert.deepEqual(navigationForKey(next, "target9:limit40"), firstJournalPage("target9:limit40"));
});

test("back navigation reuses boundaries and next replaces an obsolete forward path", () => {
  const first = firstJournalPage("logs");
  const second = nextJournalPage(first, "boundary1");
  const third = nextJournalPage(second, "boundary2");
  const back = previousJournalPage(third);
  assert.equal(back.cursors[back.index], "boundary1");
  assert.deepEqual(nextJournalPage(back, "new-boundary2").cursors, [null, "boundary1", "new-boundary2"]);
  assert.equal(previousJournalPage(first).index, 0);
});
