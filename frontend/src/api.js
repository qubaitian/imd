export function workspaceDirectory(pathname = location.pathname) {
  return decodeURIComponent(pathname).replace(/\/$/, '') || '/';
}

export function workspaceUrl(path, directory = workspaceDirectory()) {
  const url = new URL(path, location.origin);
  url.searchParams.set('workspace', directory);
  return `${url.pathname}${url.search}`;
}
