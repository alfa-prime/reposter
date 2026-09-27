export type JournalNavigation = { key: string; cursors: Array<string | null>; index: number };

export function firstJournalPage(key: string): JournalNavigation {
  return { key, cursors: [null], index: 0 };
}

export function navigationForKey(state: JournalNavigation, key: string): JournalNavigation {
  return state.key === key ? state : firstJournalPage(key);
}

export function nextJournalPage(state: JournalNavigation, cursor: string): JournalNavigation {
  return { ...state, cursors: [...state.cursors.slice(0, state.index + 1), cursor], index: state.index + 1 };
}

export function previousJournalPage(state: JournalNavigation): JournalNavigation {
  return { ...state, index: Math.max(0, state.index - 1) };
}
