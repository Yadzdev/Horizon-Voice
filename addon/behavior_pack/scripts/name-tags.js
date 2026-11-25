const appliedValues = new Map();
const originalValues = new Map();

function statusSuffix(state) {
  if (!state?.connected) return "";
  if (state.muted) return " §c[MUDO]";
  if (state.speaking) return " §a[FALANDO]";
  return " §b[LINK]";
}

export function updateVoiceNameTags(players, states) {
  const stateByIdentity = new Map(states.map(state => [state.identity, state]));
  for (const player of players) {
    try {
      const identity = player.id;
      const current = String(player.nameTag || player.name);
      const previousApplied = appliedValues.get(identity);
      let base;
      if (previousApplied && current === previousApplied) {
        base = originalValues.get(identity) ?? current;
      } else {
        // Another add-on changed the tag since our last update: preserve its new value.
        base = current;
        originalValues.set(identity, base);
      }
      const next = base.replace(/ §(?:c\[MUDO\]|a\[FALANDO\]|b\[LINK\])$/, "") + statusSuffix(stateByIdentity.get(identity));
      if (next !== current) player.nameTag = next;
      originalValues.set(identity, base.replace(/ §(?:c\[MUDO\]|a\[FALANDO\]|b\[LINK\])$/, ""));
      appliedValues.set(identity, next);
    } catch (error) {
      // Invalid entities can occur during world transitions; they are retried on the next poll.
    }
  }

  const onlineIds = new Set(players.map(player => player.id));
  for (const id of appliedValues.keys()) {
    if (!onlineIds.has(id)) {
      appliedValues.delete(id);
      originalValues.delete(id);
    }
  }
}
