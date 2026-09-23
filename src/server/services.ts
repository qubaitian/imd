import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';

export interface ServiceRecord {
  pid: number;
  path: string;
  url: string;
  log: string;
  startedAt: string;
}

export interface Service extends ServiceRecord {
  number: number;
}

function isAlive(pid: number) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return (error as NodeJS.ErrnoException).code === 'EPERM';
  }
}

export function openRegistry(dir: string) {
  const recordPath = (pid: number) => path.join(dir, `${pid}.json`);
  const remove = (pid: number) => rm(recordPath(pid), { force: true });

  async function list(): Promise<Service[]> {
    const names = await readdir(dir).catch(() => []);
    const records: ServiceRecord[] = [];
    for (const name of names.filter(name => name.endsWith('.json'))) {
      const record = JSON.parse(await readFile(path.join(dir, name), 'utf8')) as ServiceRecord;
      if (isAlive(record.pid)) records.push(record);
      else await remove(record.pid);
    }
    return records
      .sort((a, b) => a.startedAt.localeCompare(b.startedAt) || a.pid - b.pid)
      .map((record, index) => ({ ...record, number: index + 1 }));
  }

  return {
    list,
    remove,
    async add(record: ServiceRecord) {
      await mkdir(dir, { recursive: true });
      await writeFile(recordPath(record.pid), JSON.stringify(record));
    },
    async close(number?: number) {
      const services = (await list()).filter(service => number === undefined || service.number === number);
      for (const service of services) {
        try {
          process.kill(service.pid, 'SIGTERM');
        } catch {
          // The process has already ended.
        }
        await remove(service.pid);
      }
      return services;
    },
  };
}
