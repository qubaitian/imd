import { existsSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';

export interface Document {
  path: string;
  read(): Promise<string>;
  save(content: string): Promise<void>;
}

function timestamp(date: Date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 23).replace('T', '_').replace(/[:.]/g, '-');
}

export function tempDirFor(cwd: string, tempRoot: string) {
  const absoluteCwd = path.resolve(cwd);
  return path.join(tempRoot, path.relative(path.parse(absoluteCwd).root, absoluteCwd));
}

async function createTempFile(cwd: string, tempRoot: string) {
  const tempDir = tempDirFor(cwd, tempRoot);
  await mkdir(tempDir, { recursive: true });
  for (;;) {
    const filePath = path.join(tempDir, `${timestamp(new Date())}.md`);
    if (!existsSync(filePath)) {
      await writeFile(filePath, '');
      return filePath;
    }
    await delay(1);
  }
}

export async function openDocument({
  cwd,
  filename,
  tempRoot = '/tmp',
}: {
  cwd: string;
  filename?: string;
  tempRoot?: string;
}): Promise<Document> {
  const filePath = filename === undefined ? await createTempFile(cwd, tempRoot) : path.resolve(cwd, filename);
  return {
    path: filePath,
    read: async () => (existsSync(filePath) ? readFile(filePath, 'utf8') : ''),
    save: content => writeFile(filePath, content, 'utf8'),
  };
}
