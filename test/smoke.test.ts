import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdtemp, readFile, realpath, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

const imd = fileURLToPath(new URL('../bin/imd.ts', import.meta.url));
const run = promisify(execFile);

test(
  'imd opens, lists, and closes background services',
  { skip: process.platform === 'win32', timeout: 10000 },
  async () => {
    const dir = await realpath(await mkdtemp(path.join(tmpdir(), 'imd-smoke-')));
    const tempDir = path.join('/tmp', dir);
    const browser = process.platform === 'darwin' ? 'open' : 'xdg-open';
    await writeFile(path.join(dir, browser), '#!/bin/sh\nexit 0\n', { mode: 0o755 });
    const env = { ...process.env, PATH: `${dir}${path.delimiter}${process.env.PATH}` };
    const imdRun = async (...args: string[]) => (await run(process.execPath, [imd, ...args], { cwd: dir, env })).stdout;
    const ownNumbers = async () =>
      (await imdRun('list'))
        .split('\n')
        .filter(line => line.includes(dir))
        .map(line => line.split(' ')[0]);

    try {
      const opened = await imdRun('open', 'note.md');
      const url = new URL(opened.match(/Open (http\S+)/)![1]);
      const saved = await fetch(new URL('/api/document', url), {
        method: 'PUT',
        headers: { Authorization: `Bearer ${url.hash.slice(1)}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: '# Smoke\n' }),
      });
      assert.equal(saved.status, 204);
      assert.equal(await readFile(path.join(dir, 'note.md'), 'utf8'), '# Smoke\n');
      assert.ok(existsSync(path.join(tempDir, 'note.md.log')));

      assert.ok((await imdRun('open', 'note.md')).includes(`Open ${url.href}`));
      await imdRun('open');
      assert.equal((await ownNumbers()).length, 2);

      for (const number of (await ownNumbers()).reverse()) await imdRun('close', number);
      assert.deepEqual(await ownNumbers(), []);
      await assert.rejects(fetch(url));
    } finally {
      for (const number of (await ownNumbers().catch(() => [])).reverse()) await imdRun('close', number);
      await rm(dir, { recursive: true, force: true });
      await rm(tempDir, { recursive: true, force: true });
    }
  },
);
