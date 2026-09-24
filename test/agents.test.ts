import assert from 'node:assert/strict';
import { mkdtemp, realpath, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, beforeEach, test } from 'node:test';
import { withAgents, type AgentShell } from '../src/server/agents.ts';
import { openShell, type Shell } from '../src/server/shell.ts';

const skip = process.platform === 'win32';
let dir: string;
let configPath: string;
let shell: Shell;
let agents: AgentShell;

const writeConfig = (config: object) => writeFile(configPath, JSON.stringify(config));

beforeEach(async () => {
  dir = await realpath(await mkdtemp(path.join(tmpdir(), 'imd-agents-')));
  configPath = path.join(dir, 'agents.json');
  await writeConfig({
    echo: { start: "sed 's/^/start: /'", continue: "sed 's/^/continue: /'" },
    picky: { start: 'grep -qx ok && echo started', continue: "sed 's/^/continue: /'" },
    group: { start: 'cat && echo end', continue: 'cat' },
  });
  shell = await openShell({ cwd: dir, env: process.env });
  agents = withAgents(shell, { configPath });
});

afterEach(async () => {
  await shell.close();
  await rm(dir, { recursive: true, force: true });
});

test('the first run of an agent uses start and later runs use continue', { skip }, async () => {
  assert.equal((await agents.run({ info: 'echo', code: 'hi' })).output, 'start: hi');
  assert.equal((await agents.run({ info: 'echo md', code: 'again' })).output, 'continue: again');
});

test('an agent starts again after a failed start', { skip }, async () => {
  assert.equal((await agents.run({ info: 'picky', code: 'no' })).reason, 'failed');
  assert.equal((await agents.run({ info: 'picky', code: 'ok' })).output, 'started');
  assert.equal((await agents.run({ info: 'picky', code: 'x' })).output, 'continue: x');
});

test('each agent starts on its own', { skip }, async () => {
  await agents.run({ info: 'echo', code: 'a' });
  assert.equal((await agents.run({ info: 'group', code: 'b' })).output, 'b\nend');
});

test('the prompt goes to the whole command without shell expansion', { skip }, async () => {
  const prompt = "$HOME `ls` 'quote'\nline two";
  assert.equal((await agents.run({ info: 'group', code: prompt })).output, `${prompt}\nend`);
});

test('the agent runs in the shared shell', { skip }, async () => {
  await agents.run({ info: 'sh', code: 'mkdir sub\ncd sub' });
  await writeConfig({ pwd: { start: 'cat >/dev/null; pwd', continue: 'pwd' } });
  assert.equal((await agents.run({ info: 'pwd', code: 'x' })).output, path.join(dir, 'sub'));
});

test('other code blocks run as shell code', { skip }, async () => {
  assert.equal((await agents.run({ info: 'sh', code: 'echo $((1 + 1))' })).output, '2');
  assert.equal((await agents.run({ info: '', code: 'echo plain' })).output, 'plain');
});

test('a missing config means no agents', { skip }, async () => {
  const none = withAgents(shell, { configPath: path.join(dir, 'missing.json') });
  assert.deepEqual(await none.names(), []);
  assert.equal((await none.run({ info: 'echo', code: 'echo shell' })).output, 'shell');
});

test('a broken config fails the agent run with a message', { skip }, async () => {
  await writeFile(configPath, '{ not json');
  const result = await agents.run({ info: 'echo', code: 'hi' });
  assert.equal(result.reason, 'failed');
  assert.match(result.output, /agent config/);
  assert.deepEqual(await agents.names(), []);
});

test('names lists the agents and follows config changes', { skip }, async () => {
  assert.deepEqual(await agents.names(), ['echo', 'picky', 'group']);
  await writeConfig({ other: { start: 'cat', continue: 'cat' } });
  assert.deepEqual(await agents.names(), ['other']);
});
