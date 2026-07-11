import { api } from '../api.js';
import { setAuth, getRole } from '../utils/auth.js';

// Helper: build a minimal fetch mock response
function mockResponse({ status = 200, ok = true, body = {}, textBody = '' } = {}) {
  return {
    ok,
    status,
    json: body instanceof Error
      ? () => Promise.reject(body)
      : () => Promise.resolve(body),
    text: () => Promise.resolve(textBody),
  };
}

beforeEach(() => {
  localStorage.clear();
  vi.resetAllMocks();
  // Stub globalThis.location so the 401 handler can write to .href
  Object.defineProperty(globalThis, 'location', {
    value: { href: '' },
    writable: true,
    configurable: true,
  });
  globalThis.fetch = vi.fn();
});

describe('GET request', () => {
  it('does not attach an Authorization header (auth rides on the httpOnly cookie)', async () => {
    setAuth('cpo', 3600);
    globalThis.fetch.mockResolvedValue(mockResponse({ status: 200, ok: true, body: {} }));

    await api.get('/test');

    expect(fetch).toHaveBeenCalledOnce();
    const [, options] = fetch.mock.calls[0];
    expect(options.headers.Authorization).toBeUndefined();
  });
});

describe('POST request', () => {
  it('serialises body as JSON and sets Content-Type', async () => {
    globalThis.fetch.mockResolvedValue(mockResponse({ status: 200, ok: true, body: {} }));

    await api.post('/test', { x: 1 });

    expect(fetch).toHaveBeenCalledOnce();
    const [, options] = fetch.mock.calls[0];
    expect(options.headers['Content-Type']).toBe('application/json');
    expect(options.body).toBe('{"x":1}');
  });
});

describe('401 response', () => {
  it('clears the auth marker from localStorage', async () => {
    setAuth('cpo', 3600);
    globalThis.fetch.mockResolvedValue(
      mockResponse({ status: 401, ok: false, body: { detail: 'Unauthorized' } })
    );

    await api.get('/protected');

    expect(getRole()).toBeNull();
  });

  it('redirects to /login', async () => {
    setAuth('cpo', 3600);
    globalThis.fetch.mockResolvedValue(
      mockResponse({ status: 401, ok: false, body: { detail: 'Unauthorized' } })
    );

    await api.get('/protected');

    expect(globalThis.location.href).toBe('/login');
  });
});

describe('204 response', () => {
  it('resolves to null', async () => {
    globalThis.fetch.mockResolvedValue({ ok: true, status: 204 });

    const result = await api.delete('/resource/1');

    expect(result).toBeNull();
  });
});

describe('non-OK response with JSON detail', () => {
  it('throws an Error with the detail message', async () => {
    globalThis.fetch.mockResolvedValue(
      mockResponse({ status: 400, ok: false, body: { detail: 'bad' } })
    );

    await expect(api.post('/submit', {})).rejects.toThrow('bad');
  });
});

describe('non-OK response with non-JSON body', () => {
  it('throws an Error', async () => {
    globalThis.fetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.reject(new Error('not json')),
      text: () => Promise.resolve('Server error'),
    });

    await expect(api.get('/broken')).rejects.toThrow();
  });
});
