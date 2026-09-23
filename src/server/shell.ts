import headless from '@xterm/headless';
import { execFile } from 'node:child_process';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { promisify } from 'node:util';
import * as pty from 'node-pty';

export type RunReason = 'done' | 'failed' | 'stopped' | 'timeout';

export interface RunResult {
  output: string;
  exitCode: number;
  reason: RunReason;
}

export interface Shell {
  run(code: string, onData?: (data: string) => void): Promise<RunResult>;
  write(data: string): void;
  resize(cols: number, rows: number): void;
  stop(): void;
  close(): Promise<void>;
}

const execFileAsync = promisify(execFile);
const mark = '\x1b]777;imd-done;';
const bell = '\x07';

const zshenv = 'unsetopt global_rcs\n';
const zshrc = `unsetopt zle prompt_sp prompt_cr
PS1='' PS2='' RPS1='' PROMPT_EOL_MARK=''
unset HISTFILE
if [[ -n $IMD_ZDOTDIR ]]; then ZDOTDIR=$IMD_ZDOTDIR; else unset ZDOTDIR; fi
unset IMD_ZDOTDIR
precmd() { local s=$?; stty -echo; printf '\\e]777;imd-done;%s\\a' $s }
preexec() { stty echo }
`;

function openHeredoc(chunk: string) {
  const waiting: { word: string; dash: boolean }[] = [];
  for (const line of chunk.split('\n')) {
    if (waiting.length > 0) {
      if ((waiting[0].dash ? line.replace(/^\t+/, '') : line) === waiting[0].word) waiting.shift();
      continue;
    }
    for (const match of line.matchAll(/(?<!<)<<(?!<)(-?)\s*(['"]?)([\w.-]+)\2/g))
      waiting.push({ dash: match[1] === '-', word: match[3] });
  }
  return waiting.length > 0;
}

async function isComplete(chunk: string) {
  if (/(\\|&&|\|\|?)\s*$/.test(chunk) || openHeredoc(chunk)) return false;
  return execFileAsync('zsh', ['-n', '-c', chunk]).then(
    () => true,
    () => false,
  );
}

export async function splitCommands(code: string) {
  const commands: string[] = [];
  let lines: string[] = [];
  for (const line of code.split('\n')) {
    if (lines.length === 0 && line.trim() === '') continue;
    lines.push(line);
    if (await isComplete(lines.join('\n'))) {
      commands.push(lines.join('\n'));
      lines = [];
    }
  }
  if (lines.length > 0) commands.push(lines.join('\n'));
  return commands;
}

function readScreen(screen: headless.Terminal) {
  return new Promise<string>(resolve =>
    screen.write('', () => {
      const buffer = screen.buffer.active;
      let text = '';
      for (let i = 0; i < buffer.length; i++) {
        const line = buffer.getLine(i);
        text += (i > 0 && !line?.isWrapped ? '\n' : '') + (line?.translateToString(true) ?? '');
      }
      resolve(text.trimEnd());
    }),
  );
}

interface Active {
  screen: headless.Terminal;
  onData?: (data: string) => void;
  stopReason?: RunReason;
}

export async function openShell({
  cwd,
  env,
  idleMs = 60_000,
}: {
  cwd: string;
  env: NodeJS.ProcessEnv;
  idleMs?: number;
}): Promise<Shell> {
  const dir = await mkdtemp(path.join(tmpdir(), 'imd-zsh-'));
  await writeFile(path.join(dir, '.zshenv'), zshenv);
  await writeFile(path.join(dir, '.zshrc'), zshrc);
  const commandFile = path.join(dir, 'command.zsh');
  let cols = 80;
  let rows = 24;
  let term: pty.IPty | undefined;
  let ready: Promise<void> = Promise.resolve();
  let onMark: ((exitCode: number) => void) | undefined;
  let active: Active | undefined;
  let idle: NodeJS.Timeout | undefined;
  let queue: Promise<unknown> = Promise.resolve();

  function emit(data: string) {
    if (!active || data === '') return;
    active.screen.write(data);
    active.onData?.(data);
    resetIdle();
  }

  function resetIdle() {
    clearTimeout(idle);
    idle = setTimeout(() => interrupt('timeout'), idleMs);
  }

  function handle(chunk: string, pending: { text: string }) {
    let text = pending.text + chunk;
    pending.text = '';
    for (;;) {
      const at = text.indexOf(mark);
      if (at >= 0) {
        const end = text.indexOf(bell, at);
        emit(text.slice(0, at));
        if (end < 0) return void (pending.text = text.slice(at));
        onMark?.(Number(text.slice(at + mark.length, end)));
        text = text.slice(end + 1);
        continue;
      }
      const escape = text.lastIndexOf('\x1b');
      if (escape >= 0 && mark.startsWith(text.slice(escape))) {
        emit(text.slice(0, escape));
        return void (pending.text = text.slice(escape));
      }
      return emit(text);
    }
  }

  function start() {
    const pending = { text: '' };
    const next = pty.spawn('zsh', ['-i'], {
      name: 'xterm-256color',
      cwd,
      cols,
      rows,
      env: { ...env, ZDOTDIR: dir, IMD_ZDOTDIR: env.ZDOTDIR ?? '' },
    });
    term = next;
    ready = new Promise(resolve => (onMark = () => resolve()));
    next.onData(chunk => handle(chunk, pending));
    next.onExit(({ exitCode }) => {
      if (term !== next) return;
      term = undefined;
      onMark?.(exitCode || 1);
    });
  }

  function interrupt(reason: RunReason) {
    const current = active;
    if (!current || !term) return;
    current.stopReason ??= reason;
    term.write('\x03');
    const pid = term.pid;
    setTimeout(async () => {
      if (active !== current) return;
      const { stdout } = await execFileAsync('ps', ['-o', 'tpgid=', '-p', String(pid)]).catch(() => ({ stdout: '' }));
      const group = Number(stdout.trim());
      if (group > 0 && group !== pid) process.kill(-group, 'SIGKILL');
    }, 2000);
  }

  async function execute(code: string, onData?: (data: string) => void): Promise<RunResult> {
    const commands = await splitCommands(code);
    if (!term) start();
    await ready;
    const current: Active = {
      screen: new headless.Terminal({ cols, rows, scrollback: 10_000, allowProposedApi: true }),
      onData,
    };
    active = current;
    let exitCode = 0;
    try {
      for (const command of commands) {
        await writeFile(commandFile, `${command}\n`);
        if (current.stopReason) break;
        const shell = term;
        if (!shell) break;
        exitCode = await new Promise<number>(resolve => {
          onMark = resolve;
          resetIdle();
          shell.write(`. '${commandFile}'\n`);
        });
        if (current.stopReason || exitCode !== 0 || !term) break;
      }
    } finally {
      clearTimeout(idle);
      active = undefined;
      onMark = undefined;
    }
    const reason = current.stopReason ?? (exitCode === 0 && term ? 'done' : 'failed');
    const output = await readScreen(current.screen);
    current.screen.dispose();
    return { output, exitCode, reason };
  }

  start();
  await ready;
  return {
    run(code, onData) {
      const result = queue.then(() => execute(code, onData));
      queue = result.catch(() => undefined);
      return result;
    },
    write(data) {
      if (active) term?.write(data);
    },
    resize(nextCols, nextRows) {
      cols = nextCols;
      rows = nextRows;
      term?.resize(cols, rows);
      active?.screen.resize(cols, rows);
    },
    stop: () => interrupt('stopped'),
    async close() {
      const current = term;
      term = undefined;
      current?.kill();
      clearTimeout(idle);
      await rm(dir, { recursive: true, force: true });
    },
  };
}
