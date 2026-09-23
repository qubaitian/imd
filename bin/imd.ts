#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { closeSync, existsSync, openSync } from 'node:fs';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { openDocument, tempDirFor } from '../src/server/document.ts';
import { startEditor } from '../src/server/server.ts';
import { openRegistry } from '../src/server/services.ts';

const usage = `Usage:
  imd open [filename]
  imd list
  imd close [number]`;

function openBrowser(url: string) {
  const [command, ...args] =
    process.platform === 'darwin'
      ? ['open', url]
      : process.platform === 'win32'
        ? ['cmd', '/c', 'start', '', url]
        : ['xdg-open', url];
  spawn(command, args, { stdio: 'ignore' }).on('error', () =>
    console.error('Could not open a browser. Use the URL above.'),
  );
}

function exitWith(message: string): never {
  console.error(message);
  process.exit(1);
}

function showOpened(filePath: string, url: string) {
  console.log(`Editing ${filePath}`);
  console.log(`Open ${url}`);
  openBrowser(url);
}

const [command, ...args] = process.argv.slice(2);
const cwd = process.cwd();
const tempRoot = '/tmp';
const registry = openRegistry(path.join(tempRoot, 'imd', 'services'));
const distDir = fileURLToPath(new URL('../dist', import.meta.url));

async function open(filename?: string) {
  if (!existsSync(path.join(distDir, 'index.html'))) exitWith('Build the editor first with npm run build.');
  if (filename !== undefined) {
    const running = (await registry.list()).find(service => service.path === path.resolve(cwd, filename));
    if (running) return showOpened(running.path, running.url);
  }

  const document = await openDocument({ cwd, filename, tempRoot });
  const logDir = tempDirFor(cwd, tempRoot);
  await mkdir(logDir, { recursive: true });
  const log = path.join(logDir, `${path.basename(document.path)}.log`);
  const logFd = openSync(log, 'a');
  const child = spawn(process.execPath, [fileURLToPath(import.meta.url), 'serve', document.path, log], {
    cwd,
    detached: true,
    stdio: ['ignore', logFd, logFd, 'ipc'],
  });
  closeSync(logFd);
  const [message] = await Promise.race([
    once(child, 'message'),
    once(child, 'exit').then(() => exitWith(`The service did not start. See ${log}`)),
  ]);
  child.disconnect();
  child.unref();
  showOpened(document.path, (message as { url: string }).url);
}

async function serve(filePath: string, log: string) {
  const document = await openDocument({ cwd, filename: filePath });
  const editor = await startEditor({ document, distDir });
  await registry.add({
    pid: process.pid,
    path: document.path,
    url: editor.url,
    log,
    startedAt: new Date().toISOString(),
  });
  console.log(`${new Date().toISOString()} Editing ${document.path}`);
  console.log(`${new Date().toISOString()} Open ${editor.url}`);
  const stop = async () => {
    await editor.close();
    await registry.remove(process.pid);
    process.exit(0);
  };
  process.on('SIGTERM', stop);
  process.on('SIGINT', stop);
  process.send?.({ url: editor.url });
}

async function list() {
  const services = await registry.list();
  if (services.length === 0) return console.log('No services.');
  for (const service of services) console.log(`${service.number} ${service.path} ${service.url} ${service.log}`);
}

async function close(number?: string) {
  if (number !== undefined && !/^[1-9]\d*$/.test(number)) exitWith(usage);
  const closed = await registry.close(number === undefined ? undefined : Number(number));
  if (number !== undefined && closed.length === 0) exitWith(`No service ${number}. Run imd list.`);
  for (const service of closed) console.log(`Closed ${service.number} ${service.path}`);
}

if (command === 'open' && args.length <= 1) await open(args[0]);
else if (command === 'serve' && args.length === 2) await serve(args[0], args[1]);
else if (command === 'list' && args.length === 0) await list();
else if (command === 'close' && args.length <= 1) await close(args[0]);
else exitWith(usage);
