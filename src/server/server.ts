import { serve } from '@hono/node-server';
import { serveStatic } from '@hono/node-server/serve-static';
import { Hono } from 'hono';
import { bearerAuth } from 'hono/bearer-auth';
import { randomBytes } from 'node:crypto';
import { once } from 'node:events';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import path from 'node:path';
import type { Document } from './document.ts';

export async function startEditor({
  document,
  distDir,
  port = 0,
}: {
  document: Document;
  distDir: string;
  port?: number;
}) {
  const token = randomBytes(24).toString('hex');
  const app = new Hono()
    .use('/api/*', bearerAuth({ token }))
    .get('/api/document', async c => c.json({ path: document.path, content: await document.read() }))
    .put('/api/document', async c => {
      const body = await c.req.json().catch(() => undefined);
      if (body === undefined) return c.json({ error: 'Body must be JSON.' }, 400);
      const content = body?.content;
      if (typeof content !== 'string') return c.json({ error: 'Content must be a string.' }, 400);
      await document.save(content);
      return c.body(null, 204);
    })
    .get('/*', serveStatic({ root: path.resolve(distDir) }));

  const server = serve({ fetch: app.fetch, port, hostname: '127.0.0.1' }) as Server;
  await once(server, 'listening');
  return {
    url: `http://127.0.0.1:${(server.address() as AddressInfo).port}/#${token}`,
    async close() {
      server.close();
      server.closeAllConnections();
      await once(server, 'close');
    },
  };
}
