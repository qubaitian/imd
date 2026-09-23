import assert from 'node:assert/strict';
import { mkdtemp, realpath, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, beforeEach, test } from 'node:test';
import { openShell, splitCommands, type Shell } from '../src/server/shell.ts';

const skip = process.platform === 'win32';
let dir: string;
let shell: Shell;

beforeEach(async () => {
  dir = await realpath(await mkdtemp(path.join(tmpdir(), 'imd-shell-')));
  shell = await openShell({ cwd: dir, env: { ...process.env, IMD_TEST: 'start' }, idleMs: 60_000 });
});

afterEach(async () => {
  await shell.close();
  await rm(dir, { recursive: true, force: true });
});

test('splitCommands keeps each complete command apart', { skip }, async () => {
  const code = [
    'ls',
    '',
    'for x in a b; do',
    '  echo $x',
    'done',
    'echo one \\',
    '  two',
    'cat <<EOF',
    'hi',
    'EOF',
    'true &&',
    '  echo yes',
  ].join('\n');
  assert.deepEqual(await splitCommands(code), [
    'ls',
    'for x in a b; do\n  echo $x\ndone',
    'echo one \\\n  two',
    'cat <<EOF\nhi\nEOF',
    'true &&\n  echo yes',
  ]);
});

test('splitCommands sends an unfinished rest as one command', { skip }, async () => {
  assert.deepEqual(await splitCommands('ls\nif true; then\necho x'), ['ls', 'if true; then\necho x']);
});

test('a run starts in the given directory and environment', { skip }, async () => {
  const result = await shell.run('pwd\necho $IMD_TEST');
  assert.deepEqual(result, { output: `${dir}\nstart`, exitCode: 0, reason: 'done' });
});

test('cd and export carry over to the next run', { skip }, async () => {
  await shell.run('mkdir sub\ncd sub\nexport IMD_TEST=changed');
  const result = await shell.run('pwd\necho $IMD_TEST');
  assert.equal(result.output, `${path.join(dir, 'sub')}\nchanged`);
});

test('the output streams to onData without the typed command', { skip }, async () => {
  let streamed = '';
  await shell.run('echo streamed', data => (streamed += data));
  assert.equal(streamed, 'streamed\r\n');
});

test('the first failure stops the run', { skip }, async () => {
  const result = await shell.run('echo a\nfalse\necho b');
  assert.deepEqual(result, { output: 'a', exitCode: 1, reason: 'failed' });
});

test('stop ends the running command and keeps the shell', { skip }, async () => {
  const running = shell.run('cd /\nsleep 30\necho never');
  setTimeout(() => shell.stop(), 300);
  const result = await running;
  assert.equal(result.reason, 'stopped');
  assert.equal((await shell.run('pwd')).output, '/');
});

test('stop kills a command that ignores Ctrl+C', { skip, timeout: 10_000 }, async () => {
  const running = shell.run(`sh -c "trap '' INT; sleep 30"`);
  setTimeout(() => shell.stop(), 300);
  assert.equal((await running).reason, 'stopped');
  assert.equal((await shell.run('echo alive')).output, 'alive');
});

test('after exit, the next run starts a new shell', { skip }, async () => {
  assert.equal((await shell.run('exit 3')).reason, 'failed');
  assert.equal((await shell.run('pwd')).output, dir);
});

test('a command with no output for idleMs times out', { skip }, async () => {
  const quick = await openShell({ cwd: dir, env: process.env, idleMs: 300 });
  try {
    const result = await quick.run('echo start\nsleep 30');
    assert.equal(result.reason, 'timeout');
    assert.match(result.output, /^start/);
  } finally {
    await quick.close();
  }
});

test('write sends input to an interactive command', { skip }, async () => {
  const running = shell.run('read name\necho hello $name');
  setTimeout(() => shell.write('imd\r'), 300);
  const result = await running;
  assert.equal(result.output, 'imd\nhello imd');
});

test('runs wait in a queue', { skip }, async () => {
  const [first, second] = await Promise.all([shell.run('sleep 0.2\necho 1'), shell.run('echo 2')]);
  assert.equal(first.output, '1');
  assert.equal(second.output, '2');
});

test('progress bars keep only the final text', { skip }, async () => {
  const result = await shell.run("printf '10%%\\r50%%\\r100%%\\n'");
  assert.equal(result.output, '100%');
});
