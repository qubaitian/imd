import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, beforeEach, test } from 'node:test';
import { startEditor } from '../src/server/server.ts';

let distDir: string;
let editor: Awaited<ReturnType<typeof startEditor>>;
let saved: string[];
let base: string;
let headers: Record<string, string>;

beforeEach(async () => {
  distDir = await mkdtemp(path.join(tmpdir(), 'imd-dist-'));
  await writeFile(path.join(distDir, 'index.html'), '<h1>IMD</h1>');
  saved = [];
  const document = {
    path: '/doc.md',
    read: async () => '# Doc',
    save: async (content: string) => {
      saved.push(content);
    },
  };
  editor = await startEditor({ document, distDir });
  const url = new URL(editor.url);
  base = url.origin;
  headers = { Authorization: `Bearer ${url.hash.slice(1)}` };
});

afterEach(async () => {
  await editor.close();
  await rm(distDir, { recursive: true, force: true });
});

function put(body: string) {
  return fetch(`${base}/api/document`, {
    method: 'PUT',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body,
  });
}

test('it serves index.html at the root', async () => {
  const response = await fetch(`${base}/`);
  assert.equal(response.status, 200);
  assert.match(response.headers.get('content-type') ?? '', /^text\/html/);
  assert.equal(await response.text(), '<h1>IMD</h1>');
});

test('it returns 404 for missing files, paths outside dist, and other methods', async () => {
  assert.equal((await fetch(`${base}/missing.js`)).status, 404);
  assert.equal((await fetch(`${base}/%2e%2e/secret`)).status, 404);
  assert.equal((await fetch(`${base}/`, { method: 'POST' })).status, 404);
  assert.equal((await fetch(`${base}/api/document`, { method: 'DELETE', headers })).status, 404);
});

test('the document API needs the token', async () => {
  assert.equal((await fetch(`${base}/api/document`)).status, 401);
});

test('GET returns the document path and content', async () => {
  const response = await fetch(`${base}/api/document`, { headers });
  assert.deepEqual(await response.json(), { path: '/doc.md', content: '# Doc' });
});

test('PUT saves the content', async () => {
  assert.equal((await put(JSON.stringify({ content: '# New' }))).status, 204);
  assert.deepEqual(saved, ['# New']);
});

test('PUT rejects content that is not a string', async () => {
  assert.equal((await put(JSON.stringify({ content: 1 }))).status, 400);
  assert.deepEqual(saved, []);
});

test('an unexpected error returns 500 and the server keeps running', async () => {
  assert.equal((await put('not json')).status, 500);
  assert.equal((await fetch(`${base}/api/document`, { headers })).status, 200);
});
