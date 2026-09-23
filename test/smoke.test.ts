import assert from 'node:assert/strict';
import { type ChildProcessWithoutNullStreams, spawn } from 'node:child_process';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const imd = fileURLToPath(new URL('../bin/imd.ts', import.meta.url));

function waitForUrl(child: ChildProcessWithoutNullStreams) {
  return new Promise<string>((resolve, reject) => {
    let output = '';
    child.stdout.on('data', chunk => {
      output += chunk;
      const match = output.match(/Open (http\S+)/);
      if (match) resolve(match[1]);
    });
    child.once('exit', code => reject(new Error(`imd exited with ${code}.`)));
  });
}

test('imd open serves and saves a file', { skip: process.platform === 'win32', timeout: 5000 }, async () => {
  const dir = await mkdtemp(path.join(tmpdir(), 'imd-smoke-'));
  const browser = process.platform === 'darwin' ? 'open' : 'xdg-open';
  await writeFile(path.join(dir, browser), '#!/bin/sh\nexit 0\n', { mode: 0o755 });
  const child = spawn(process.execPath, [imd, 'open', 'note.md'], {
    cwd: dir,
    env: { ...process.env, PATH: `${dir}${path.delimiter}${process.env.PATH}` },
  });

  try {
    const url = new URL(await waitForUrl(child));
    const saved = await fetch(new URL('/api/document', url), {
      method: 'PUT',
      headers: { Authorization: `Bearer ${url.hash.slice(1)}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: '# Smoke\n' }),
    });
    assert.equal(saved.status, 204);
    assert.equal(await readFile(path.join(dir, 'note.md'), 'utf8'), '# Smoke\n');
  } finally {
    child.kill('SIGKILL');
    await rm(dir, { recursive: true, force: true });
  }
});
