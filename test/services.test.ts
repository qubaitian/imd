import assert from 'node:assert/strict';
import { type ChildProcess, spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, beforeEach, test } from 'node:test';
import { openRegistry } from '../src/server/services.ts';

let dir: string;
let children: ChildProcess[];

beforeEach(async () => {
  dir = await mkdtemp(path.join(tmpdir(), 'imd-services-'));
  children = [];
});

afterEach(async () => {
  for (const child of children) child.kill('SIGKILL');
  await rm(dir, { recursive: true, force: true });
});

function sleeper() {
  const child = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], { stdio: 'ignore' });
  children.push(child);
  return child;
}

function record(pid: number, name: string, startedAt: string) {
  return { pid, path: `/${name}.md`, url: `http://${name}`, log: `/${name}.log`, startedAt };
}

test('list is empty when there are no services', async () => {
  assert.deepEqual(await openRegistry(dir).list(), []);
});

test('list numbers live services by start time', async () => {
  const registry = openRegistry(dir);
  const a = sleeper();
  const b = sleeper();
  await registry.add(record(b.pid!, 'b', '2026-09-23T02:00:00.000Z'));
  await registry.add(record(a.pid!, 'a', '2026-09-23T01:00:00.000Z'));
  const services = await registry.list();
  assert.deepEqual(
    services.map(s => [s.number, s.path]),
    [
      [1, '/a.md'],
      [2, '/b.md'],
    ],
  );
});

test('list drops services whose process has ended', async () => {
  const registry = openRegistry(dir);
  const dead = sleeper();
  dead.kill('SIGKILL');
  await once(dead, 'exit');
  await registry.add(record(dead.pid!, 'dead', '2026-09-23T01:00:00.000Z'));
  assert.deepEqual(await registry.list(), []);
});

test('close with a number stops only that service', async () => {
  const registry = openRegistry(dir);
  const a = sleeper();
  const b = sleeper();
  await registry.add(record(a.pid!, 'a', '2026-09-23T01:00:00.000Z'));
  await registry.add(record(b.pid!, 'b', '2026-09-23T02:00:00.000Z'));
  const exited = once(b, 'exit');
  const closed = await registry.close(2);
  assert.deepEqual(
    closed.map(s => s.path),
    ['/b.md'],
  );
  await exited;
  assert.deepEqual(
    (await registry.list()).map(s => s.path),
    ['/a.md'],
  );
});

test('close without a number stops all services', async () => {
  const registry = openRegistry(dir);
  const a = sleeper();
  const b = sleeper();
  await registry.add(record(a.pid!, 'a', '2026-09-23T01:00:00.000Z'));
  await registry.add(record(b.pid!, 'b', '2026-09-23T02:00:00.000Z'));
  const exited = Promise.all([once(a, 'exit'), once(b, 'exit')]);
  assert.equal((await registry.close()).length, 2);
  await exited;
  assert.deepEqual(await registry.list(), []);
});

test('close with an unknown number stops nothing', async () => {
  const registry = openRegistry(dir);
  const a = sleeper();
  await registry.add(record(a.pid!, 'a', '2026-09-23T01:00:00.000Z'));
  assert.deepEqual(await registry.close(5), []);
  assert.equal((await registry.list()).length, 1);
});

test('remove deletes a service record', async () => {
  const registry = openRegistry(dir);
  const a = sleeper();
  await registry.add(record(a.pid!, 'a', '2026-09-23T01:00:00.000Z'));
  await registry.remove(a.pid!);
  assert.deepEqual(await registry.list(), []);
});
