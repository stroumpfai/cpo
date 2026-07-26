// Remembers what a team member typed on a given team link, so they don't have
// to retype it every pizza day. Name and email are stored separately: if the
// CPO flips member_identifier, we must never prefill an email field with a name.
//
// Shape: { "<unique_link>": { name: string, email: string }, ... }
const IDENTITY_KEY = 'cpo_member_identity';

const EMPTY = { name: '', email: '' };

function readAll() {
  try {
    const parsed = JSON.parse(localStorage.getItem(IDENTITY_KEY));
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

export function getMemberIdentity(link) {
  if (!link) return { ...EMPTY };
  const all = readAll();
  // hasOwn, not a plain lookup: `link` comes straight off the URL, so
  // /orders/__proto__ would otherwise read through to Object.prototype.
  const entry = Object.hasOwn(all, link) ? all[link] : null;
  return {
    name:  typeof entry?.name  === 'string' ? entry.name  : '',
    email: typeof entry?.email === 'string' ? entry.email : '',
  };
}

export function setMemberIdentity(link, field, value) {
  if (!link || (field !== 'name' && field !== 'email')) return;
  try {
    const all = readAll();
    all[link] = { ...getMemberIdentity(link), [field]: value };
    localStorage.setItem(IDENTITY_KEY, JSON.stringify(all));
  } catch {
    // Private mode or quota exceeded — remembering the value is a convenience,
    // never a reason to break the order.
  }
}

export function clearMemberIdentity(link) {
  if (!link) return;
  try {
    const all = readAll();
    delete all[link];
    localStorage.setItem(IDENTITY_KEY, JSON.stringify(all));
  } catch {
    // ignore
  }
}
