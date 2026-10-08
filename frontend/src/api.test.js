import { afterEach, expect, it, vi } from 'vitest';
import { workspaceDirectory, workspaceUrl } from './api.js';

afterEach(() => vi.unstubAllGlobals());

it('keeps the directory URL and document path separate', () => {
  vi.stubGlobal('location', {
    origin: 'http://localhost:8000',
    pathname: '/Users/me/notes%20with%20%E7%A9%BA%E6%A0%BC/',
  });
  expect(workspaceDirectory()).toBe('/Users/me/notes with 空格');
  const url = new URL(workspaceUrl('/api/document?path=sub%2Fimd.md'), location.origin);
  expect(url.pathname).toBe('/api/document');
  expect(url.searchParams.get('path')).toBe('sub/imd.md');
  expect(url.searchParams.get('workspace')).toBe('/Users/me/notes with 空格');
});

it('supports the filesystem root directory', () => {
  expect(workspaceDirectory('/')).toBe('/');
});
