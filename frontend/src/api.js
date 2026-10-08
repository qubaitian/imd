export function workspaceDirectory(pathname = location.pathname) {
  return decodeURIComponent(pathname).replace(/\/$/, '') || '/';
}

export function workspaceUrl(path, directory = workspaceDirectory()) {
  const url = new URL(path, location.origin);
  url.searchParams.set('workspace', directory);
  return `${url.pathname}${url.search}`;
}

export async function readResponse(response) {
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error(response.ok
      ? 'The IMD service returned invalid JSON. See the service log.'
      : `The IMD service returned HTTP ${response.status}. See the service log.`);
  }
  if (!response.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : `The IMD service returned HTTP ${response.status}. See the service log.`);
  return body;
}
