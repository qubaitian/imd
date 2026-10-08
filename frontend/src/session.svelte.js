export class DocumentSession {
  connected = $state(false);
  state = $state('connecting');
  cwd = $state('');
  runs = $state({});

  constructor(path, onDocument, onError) {
    this.path = path;
    this.onDocument = onDocument;
    this.onError = onError;
    this.connect();
  }

  connect() {
    if (this.disposed) return;
    this.state = 'connecting';
    this.socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/session?path=${encodeURIComponent(this.path)}`);
    this.socket.onmessage = ({ data }) => {
      if (this.disposed) return;
      const event = JSON.parse(data);
      if (event.type === 'snapshot') {
        this.connected = true;
        this.state = event.state;
        this.cwd = event.cwd;
        this.runs = Object.fromEntries(event.runs.filter((run) => run.block_id).map((run) => [run.block_id, run]));
        this.send({ type: 'resize', columns: 80, rows: 20 });
      } else if (event.type === 'queued' || event.type === 'running') {
        if (event.block_id && !(event.type === 'queued' && this.runs[event.block_id]?.status === 'running')) this.runs[event.block_id] = { ...event, status: event.type, output: '' };
        if (event.type === 'running') this.state = 'running';
      } else if (event.type === 'output') {
        const run = this.runs[event.block_id];
        if (run?.id === event.id) run.output = (run.output + event.data).slice(-1_000_000);
      } else if (event.type === 'done') {
        this.state = 'ready';
        this.cwd = event.cwd;
        if (event.block_id) this.runs[event.block_id] = { ...this.runs[event.block_id], ...event };
      } else if (event.type === 'document') {
        this.onDocument(event.document);
      } else if (event.type === 'error' || event.type === 'save_error') {
        const run = this.runs[event.block_id];
        if (run?.id === event.id) this.runs[event.block_id] = { ...run, status: 'error', text: event.text ?? run.text ?? '', saveError: event.message };
        this.onError(event.message);
      } else if (event.type === 'closed') {
        this.connected = false;
        this.state = 'closed';
      }
    };
    this.socket.onclose = ({ code }) => {
      if (this.disposed) return;
      this.connected = false;
      this.state = 'disconnected';
      if (code === 1008) this.onError('Cannot connect to this document session.');
      else this.reconnect = setTimeout(() => this.connect(), 1000);
    };
  }

  send(message) {
    if (this.socket?.readyState !== WebSocket.OPEN) return false;
    this.socket.send(JSON.stringify(message));
    return true;
  }

  run(document, blockId) {
    const id = crypto.randomUUID();
    if (this.runs[blockId]?.status !== 'running') this.runs[blockId] = { id, block_id: blockId, status: 'queued', output: '' };
    return this.send({ type: 'run', id, block_id: blockId, content: document.content, revision: document.revision });
  }

  input(id, data) {
    if (Object.values(this.runs).some((run) => run.id === id && run.status === 'running')) {
      this.send({ type: data === '\x03' ? 'interrupt' : 'input', data });
    }
  }

  resize(id, columns, rows) {
    if (Object.values(this.runs).some((run) => run.id === id && run.status === 'running')) {
      this.send({ type: 'resize', columns: Math.min(500, Math.max(2, columns)), rows: Math.min(200, Math.max(2, rows)) });
    }
  }

  async reset() {
    const response = await fetch(`/api/session/reset?path=${encodeURIComponent(this.path)}`, { method: 'POST' });
    if (!response.ok) this.onError((await response.json()).detail);
    else this.runs = {};
  }

  close() {
    this.disposed = true;
    clearTimeout(this.reconnect);
    this.socket?.close();
  }
}
