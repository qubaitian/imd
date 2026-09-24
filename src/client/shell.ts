import type { RunResult } from '../server/shell.ts';

export type { RunResult };

interface PendingRun {
  backlog: string[];
  listener?: (data: string) => void;
  resolve: (result: RunResult) => void;
}

export type ShellClient = ReturnType<typeof connectShell>;

export function connectShell(token: string) {
  const runs = new Map<string, PendingRun>();
  let socket: WebSocket | undefined;
  let opened: Promise<WebSocket> | undefined;

  function open() {
    if (socket && opened) return opened;
    const next = new WebSocket(`${location.origin.replace(/^http/, 'ws')}/shell`);
    socket = next;
    opened = new Promise(resolve =>
      next.addEventListener('open', () => {
        next.send(JSON.stringify({ type: 'auth', token }));
        resolve(next);
      }),
    );
    next.addEventListener('message', event => {
      const message = JSON.parse(String(event.data));
      const run = runs.get(message.runId);
      if (!run) return;
      if (message.type === 'data') {
        if (run.listener) run.listener(message.data);
        else run.backlog.push(message.data);
      } else if (message.type === 'done') {
        runs.delete(message.runId);
        run.resolve({ output: message.output, exitCode: message.exitCode, reason: message.reason });
      }
    });
    next.addEventListener('close', () => {
      socket = opened = undefined;
      for (const run of runs.values())
        run.resolve({ output: 'The connection to IMD closed.', exitCode: 1, reason: 'failed' });
      runs.clear();
    });
    return opened;
  }

  const send = async (message: object) => (await open()).send(JSON.stringify(message));

  return {
    run(runId: string, info: string, code: string) {
      const done = new Promise<RunResult>(resolve => runs.set(runId, { backlog: [], resolve }));
      void send({ type: 'run', runId, info, code });
      return done;
    },
    listen(runId: string, listener: (data: string) => void) {
      const run = runs.get(runId);
      if (!run) return () => undefined;
      run.listener = listener;
      for (const data of run.backlog.splice(0)) listener(data);
      return () => {
        run.listener = undefined;
      };
    },
    input: (data: string) => void send({ type: 'input', data }),
    stop: () => void send({ type: 'stop' }),
    resize: (cols: number, rows: number) => void send({ type: 'resize', cols, rows }),
  };
}
