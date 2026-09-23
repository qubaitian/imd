import { serve, upgradeWebSocket } from '@hono/node-server';
import { serveStatic } from '@hono/node-server/serve-static';
import { Hono } from 'hono';
import { bearerAuth } from 'hono/bearer-auth';
import type { WSContext } from 'hono/ws';
import { randomBytes, timingSafeEqual } from 'node:crypto';
import { once } from 'node:events';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import path from 'node:path';
import { WebSocketServer } from 'ws';
import type { Document } from './document.ts';
import { openShell, type Shell } from './shell.ts';

type ShellMessage =
  | { type: 'auth'; token: string }
  | { type: 'run'; runId: string; code: string }
  | { type: 'input'; data: string }
  | { type: 'stop' }
  | { type: 'resize'; cols: number; rows: number };

function parse(data: unknown): ShellMessage | undefined {
  try {
    const message = JSON.parse(String(data));
    return typeof message?.type === 'string' ? message : undefined;
  } catch {
    return undefined;
  }
}

export async function startEditor({
  document,
  distDir,
  port = 0,
  cwd = process.cwd(),
  env = process.env,
}: {
  document: Document;
  distDir: string;
  port?: number;
  cwd?: string;
  env?: NodeJS.ProcessEnv;
}) {
  const token = randomBytes(24).toString('hex');
  const sameToken = (candidate: string) =>
    candidate.length === token.length && timingSafeEqual(Buffer.from(candidate), Buffer.from(token));
  let shell: Promise<Shell> | undefined;
  const getShell = () => (shell ??= openShell({ cwd, env }));

  function shellSocket() {
    let authed = false;
    let pending = 0;
    const send = (ws: WSContext, message: object) => {
      if (ws.readyState === 1) ws.send(JSON.stringify(message));
    };
    return {
      async onMessage(event: { data: unknown }, ws: WSContext) {
        const message = parse(event.data);
        if (!authed) {
          authed = message?.type === 'auth' && typeof message.token === 'string' && sameToken(message.token);
          if (!authed) ws.close(1008, 'Unauthorized');
          return;
        }
        const current = await getShell();
        if (message?.type === 'run' && typeof message.code === 'string') {
          const { runId } = message;
          pending++;
          const result = await current
            .run(message.code, data => send(ws, { type: 'data', runId, data }))
            .finally(() => pending--);
          send(ws, { type: 'done', runId, ...result });
        } else if (message?.type === 'input' && typeof message.data === 'string') current.write(message.data);
        else if (message?.type === 'stop') current.stop();
        else if (message?.type === 'resize' && message.cols > 0 && message.rows > 0)
          current.resize(message.cols, message.rows);
      },
      async onClose() {
        if (pending > 0) (await shell)?.stop();
      },
    };
  }

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
    .get('/shell', upgradeWebSocket(shellSocket))
    .get('/*', serveStatic({ root: path.resolve(distDir) }));

  const websocket = new WebSocketServer({ noServer: true });
  const server = serve({ fetch: app.fetch, port, hostname: '127.0.0.1', websocket: { server: websocket } }) as Server;
  await once(server, 'listening');
  return {
    url: `http://127.0.0.1:${(server.address() as AddressInfo).port}/#${token}`,
    async close() {
      for (const client of websocket.clients) client.terminate();
      server.close();
      server.closeAllConnections();
      await once(server, 'close');
      await (await shell)?.close();
    },
  };
}
