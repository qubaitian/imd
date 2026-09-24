import { randomBytes } from 'node:crypto';
import { readFile, rm, writeFile } from 'node:fs/promises';
import { homedir, tmpdir } from 'node:os';
import path from 'node:path';
import type { RunResult, Shell } from './shell.ts';

export interface Agent {
  start: string;
  continue: string;
}

export interface AgentShell {
  run(block: { info: string; code: string }, onData?: (data: string) => void): Promise<RunResult>;
  names(): Promise<string[]>;
}

export const defaultAgentConfig = path.join(homedir(), '.config', 'imd', 'agents.json');

async function readConfig(configPath: string): Promise<Record<string, Agent>> {
  let text: string;
  try {
    text = await readFile(configPath, 'utf8');
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return {};
    throw error;
  }
  const config = JSON.parse(text);
  if (typeof config !== 'object' || config === null || Array.isArray(config))
    throw new Error('The config must be a JSON object.');
  for (const [name, agent] of Object.entries<Partial<Agent> | null>(config))
    if (typeof agent?.start !== 'string' || typeof agent?.continue !== 'string')
      throw new Error(`Agent ${name} needs a start and a continue command.`);
  return config;
}

const quote = (text: string) => `'${text.replaceAll("'", `'\\''`)}'`;

export function withAgents(shell: Shell, { configPath = defaultAgentConfig } = {}): AgentShell {
  const started = new Set<string>();

  async function runAgent(name: string, agent: Agent, code: string, onData?: (data: string) => void) {
    const promptFile = path.join(tmpdir(), `imd-prompt-${randomBytes(6).toString('hex')}.md`);
    await writeFile(promptFile, `${code}\n`);
    try {
      const command = started.has(name) ? agent.continue : agent.start;
      const result = await shell.run(`{ ${command}\n} < ${quote(promptFile)}`, onData);
      if (result.reason === 'done') started.add(name);
      return result;
    } finally {
      await rm(promptFile, { force: true });
    }
  }

  return {
    async run({ info, code }, onData) {
      const name = info.split(/\s+/)[0];
      let config: Record<string, Agent>;
      try {
        config = await readConfig(configPath);
      } catch (error) {
        const output = `Could not read the agent config ${configPath}: ${(error as Error).message}`;
        return { output, exitCode: 1, reason: 'failed' };
      }
      const agent = Object.hasOwn(config, name) ? config[name] : undefined;
      return agent ? runAgent(name, agent, code, onData) : shell.run(code, onData);
    },
    async names() {
      return Object.keys(await readConfig(configPath).catch(() => ({})));
    },
  };
}
