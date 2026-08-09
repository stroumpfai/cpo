import { translateApiError } from '../../i18n/apiError.js';

// Stand-in for the `t` a component gets from useTranslation()
function makeT(dict) {
  return (key, options = {}) => {
    const template = dict[key];
    if (template === undefined) return options.defaultValue ?? key;
    return template.replace(/\{\{(\w+)\}\}/g, (_, name) => String(options[name] ?? ''));
  };
}

const t = makeT({
  'errors.session_closed': 'Bestellung geschlossen.',
  'errors.name_too_long': 'Name darf höchstens {{max}} Zeichen lang sein.',
  'errors.generic': 'Etwas ist schiefgelaufen.',
});

describe('translateApiError', () => {
  it('translates a known code', () => {
    const err = Object.assign(new Error('Session is closed'), { code: 'session_closed' });

    expect(translateApiError(err, t)).toBe('Bestellung geschlossen.');
  });

  it('interpolates params from the server', () => {
    const err = Object.assign(new Error('Name must be 100 characters or fewer.'), {
      code: 'name_too_long',
      params: { max: 100 },
    });

    expect(translateApiError(err, t)).toBe('Name darf höchstens 100 Zeichen lang sein.');
  });

  it('falls back to the English detail for a code nobody has translated yet', () => {
    const err = Object.assign(new Error('Menu is in use'), { code: 'menu_in_use' });

    expect(translateApiError(err, t)).toBe('Menu is in use');
  });

  it('falls back to the English detail when the server sends no code', () => {
    expect(translateApiError(new Error('Request failed'), t)).toBe('Request failed');
  });

  it('uses the generic message when there is nothing else to show', () => {
    expect(translateApiError(new Error(''), t)).toBe('Etwas ist schiefgelaufen.');
  });

  it('returns an empty string for no error at all', () => {
    expect(translateApiError(null, t)).toBe('');
  });
});
