import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, beforeEach, test } from 'node:test';
import { openDocument } from '../src/server/document.ts';

let tempRoot: string;
beforeEach(async () => {
  tempRoot = await mkdtemp(path.join(tmpdir(), 'imd-document-'));
});
afterEach(() => rm(tempRoot, { recursive: true, force: true }));

test('without a filename it creates an empty timestamped file under the temp root', async () => {
  const cwd = '/work/project';
  const document = await openDocument({ cwd, filename: undefined, tempRoot });
  assert.equal(path.dirname(document.path), path.join(tempRoot, 'work/project'));
  assert.match(path.basename(document.path), /^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-\d{3}\.md$/);
  assert.equal(await document.read(), '');
});

test('each temporary document gets a new file', async () => {
  const first = await openDocument({ cwd: '/work', tempRoot });
  const second = await openDocument({ cwd: '/work', tempRoot });
  assert.notEqual(first.path, second.path);
});

test('with a filename it resolves the file from cwd', async () => {
  const document = await openDocument({ cwd: tempRoot, filename: 'notes/a.md' });
  assert.equal(document.path, path.join(tempRoot, 'notes/a.md'));
});

test('a missing named file reads as empty text', async () => {
  const document = await openDocument({ cwd: tempRoot, filename: 'missing.md' });
  assert.equal(await document.read(), '');
});

test('save writes the content to the file', async () => {
  const document = await openDocument({ cwd: tempRoot, filename: 'a.md' });
  await document.save('# Hi\n');
  assert.equal(await readFile(document.path, 'utf8'), '# Hi\n');
  assert.equal(await document.read(), '# Hi\n');
});
