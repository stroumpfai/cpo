import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { createInstance } from 'i18next';
import { I18nextProvider, initReactI18next } from 'react-i18next';
import { DEFAULT_LOCALE, LOCALES, SUPPORTED_TAGS } from '../i18n/locales.js';

const resources = Object.fromEntries(
  LOCALES.map(({ tag, resource }) => [tag, { translation: resource }])
);

/**
 * A throwaway i18next instance per render — never the app singleton, so a test
 * that renders in German can't leak that language into the next test.
 * init() is synchronous here because every resource is already in memory.
 */
function createTestI18n(lng) {
  const instance = createInstance();
  instance.use(initReactI18next).init({
    resources,
    lng,
    fallbackLng: DEFAULT_LOCALE,
    supportedLngs: SUPPORTED_TAGS,
    interpolation: { escapeValue: false },
  });
  return instance;
}

/**
 * Wraps render() in a MemoryRouter with configurable initialEntries.
 *
 * The language is pinned to English by default: English copy is the source of
 * truth, so assertions here read like the UI a reviewer sees. Pass `lng` (or use
 * renderWithLanguage) to exercise a translation.
 */
export function renderWithRouter(ui, { initialEntries = ['/'], lng = DEFAULT_LOCALE } = {}) {
  const i18n = createTestI18n(lng);
  return {
    i18n,
    ...render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={initialEntries}>
          {ui}
        </MemoryRouter>
      </I18nextProvider>
    ),
  };
}

/** renderWithRouter with the language spelled out — for locale-specific tests. */
export function renderWithLanguage(ui, { lng, initialEntries = ['/'] } = {}) {
  return renderWithRouter(ui, { initialEntries, lng });
}

/**
 * Returns a set of vi.fn() mocks for the api module methods.
 * Each mock is pre-configured with mockResolvedValue from overrides,
 * falling back to {} if not provided.
 *
 * Usage in tests:
 *   vi.mock('../api.js');
 *   import api from '../api.js';
 *   ...
 *   const mocks = mockApi({ get: { data: 'value' } });
 *   api.get.mockResolvedValue(mocks.get.mock.results); // or use mocks directly
 */
export function mockApi(overrides = {}) {
  const get = vi.fn().mockResolvedValue(overrides.get ?? {});
  const post = vi.fn().mockResolvedValue(overrides.post ?? {});
  const put = vi.fn().mockResolvedValue(overrides.put ?? {});
  const del = vi.fn().mockResolvedValue(overrides.delete ?? {});

  return { get, post, put, delete: del };
}
