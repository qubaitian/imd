import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { DocumentSession } from './session.svelte.js';

let sockets;
let session;

beforeEach(() => {
  sockets = [];
  vi.useFakeTimers();
  vi.stubGlobal('location', {
    origin: 'http://localhost:8000',
    protocol: 'http:',
    host: 'localhost:8000',
    pathname: '/notes',
  });
  class Socket {
    static OPEN = 1;
    readyState = 1;
    send = vi.fn();
    close = vi.fn();
    constructor(url) {
      this.url = url;
      sockets.push(this);
    }
    message(event) {
      this.onmessage({ data: JSON.stringify(event) });
    }
  }
  vi.stubGlobal('WebSocket', Socket);
});

afterEach(() => {
  session?.close();
  session = null;
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

it.each([1000, 1006, 1012])('does not reconnect after close code %s', (code) => {
  session = new DocumentSession('imd.md', vi.fn(), vi.fn());
  sockets[0].message({ type: 'snapshot', state: 'ready', cwd: '/notes', runs: [] });
  sockets[0].onclose({ code });
  vi.advanceTimersByTime(300_000);
  expect(sockets).toHaveLength(1);
  expect(session.connected).toBe(false);
  expect(session.state).toBe('disconnected');
});

it('does not retry a failed initial connection', () => {
  session = new DocumentSession('imd.md', vi.fn(), vi.fn());
  sockets[0].onclose({ code: 1006 });
  vi.advanceTimersByTime(300_000);
  expect(sockets).toHaveLength(1);
});

it('connects once when a page creates a new document session', () => {
  session = new DocumentSession('imd.md', vi.fn(), vi.fn());
  sockets[0].onclose({ code: 1012 });
  session.close();
  session = new DocumentSession('imd.md', vi.fn(), vi.fn());
  expect(sockets).toHaveLength(2);
  expect(sockets[1].url).toBe(sockets[0].url);
  sockets[1].message({ type: 'snapshot', state: 'ready', cwd: '/notes', runs: [] });
  expect(session.connected).toBe(true);
  expect(session.state).toBe('ready');
});

it('does not reconnect a document that was closed during service downtime', () => {
  session = new DocumentSession('imd.md', vi.fn(), vi.fn());
  sockets[0].onclose({ code: 1012 });
  session.close();
  vi.advanceTimersByTime(5000);
  expect(sockets).toHaveLength(1);
});

it('connects to the new session after a reset', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ type: 'snapshot' }) })));
  session = new DocumentSession('imd.md', vi.fn(), vi.fn());
  sockets[0].message({ type: 'snapshot', state: 'ready', cwd: '/notes', runs: [] });
  const reset = session.reset();
  sockets[0].message({ type: 'closed', reason: 'The session was reset or stopped.' });
  await reset;
  sockets[0].onclose({ code: 1012 });
  expect(sockets).toHaveLength(2);
  expect(sockets[1].url).toBe(sockets[0].url);
  sockets[1].message({ type: 'snapshot', state: 'ready', cwd: '/notes', runs: [] });
  expect(session.connected).toBe(true);
  expect(session.state).toBe('ready');
});

it('stays disconnected after a failed reset', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 500, json: async () => ({ detail: 'failed' }) })));
  const onError = vi.fn();
  session = new DocumentSession('imd.md', vi.fn(), onError);
  await session.reset();
  expect(sockets).toHaveLength(1);
  expect(onError).toHaveBeenCalledWith('failed');
});

it('does not retry an unavailable document and shows the service reason', () => {
  const onError = vi.fn();
  session = new DocumentSession('interaction.md', vi.fn(), onError);
  sockets[0].onclose({ code: 1008, reason: 'Document not found. Refresh the document list.' });
  vi.advanceTimersByTime(60_000);
  expect(sockets).toHaveLength(1);
  expect(session.connected).toBe(false);
  expect(onError).toHaveBeenCalledWith('Document not found. Refresh the document list.');
});
