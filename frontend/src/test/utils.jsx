import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

/**
 * Wraps render() in a MemoryRouter with configurable initialEntries.
 */
export function renderWithRouter(ui, { initialEntries = ['/'] } = {}) {
  return {
    ...render(
      <MemoryRouter initialEntries={initialEntries}>
        {ui}
      </MemoryRouter>
    ),
  };
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
