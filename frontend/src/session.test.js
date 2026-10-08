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

it('reconnects through service downtime and accepts a fresh session after restart', () => {
  const onDocument = vi.fn();
  const onError = vi.fn();
  session = new DocumentSession('imd.md', onDocument, onError);
  sockets[0].message({ type: 'snapshot', state: 'running', cwd: '/notes', runs: [
    { id: 'old', block_id: 'abc123', status: 'running', output: 'old output' },
  ] });
  expect(session.connected).toBe(true);
  sockets[0].onclose({ code: 1012 });
  expect(session.connected).toBe(false);
  vi.advanceTimersByTime(1000);
  sockets[1].onclose({ code: 1006 });
  vi.advanceTimersByTime(1000);
  expect(sockets).toHaveLength(3);
  expect(sockets[2].url).toBe(sockets[0].url);
  sockets[2].message({ type: 'snapshot', state: 'ready', cwd: '/notes', runs: [] });
  expect(session.connected).toBe(true);
  expect(session.state).toBe('ready');
  expect(session.runs).toEqual({});
  expect(onDocument).not.toHaveBeenCalled();
  expect(onError).not.toHaveBeenCalled();
});

it('does not reconnect a document that was closed during service downtime', () => {
  session = new DocumentSession('imd.md', vi.fn(), vi.fn());
  sockets[0].onclose({ code: 1012 });
  session.close();
  vi.advanceTimersByTime(5000);
  expect(sockets).toHaveLength(1);
});
