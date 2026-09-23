#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { openDocument } from '../src/server/document.ts';
import { startEditor } from '../src/server/server.ts';

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

const args = process.argv.slice(2);
const distDir = fileURLToPath(new URL('../dist', import.meta.url));
if (args[0] !== 'open' || args.length > 2) exitWith('Usage: imd open [filename]');
if (!existsSync(path.join(distDir, 'index.html'))) exitWith('Build the editor first with npm run build.');

const document = await openDocument({ cwd: process.cwd(), filename: args[1] });
const editor = await startEditor({ document, distDir });
console.log(`Editing ${document.path}`);
console.log(`Open ${editor.url}`);
openBrowser(editor.url);
process.on('SIGINT', async () => {
  await editor.close();
  process.exit(0);
});
