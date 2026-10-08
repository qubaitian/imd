export async function copyDocumentReference(event, directory, path, clipboard = navigator.clipboard) {
  if (!event.metaKey || event.ctrlKey || event.altKey || event.shiftKey
    || event.repeat || event.isComposing || event.key.toLowerCase() !== 'l') return null;

  const { value, selectionStart: start, selectionEnd: end } = event.currentTarget;
  if (start === end) return null;
  event.preventDefault();

  const line = (offset) => value.slice(0, offset).split('\n').length;
  const reference = `@${directory.replace(/\/+$/, '')}/${path}:${line(start)}-${line(end - 1)}`;
  try {
    await clipboard.writeText(reference);
  } catch {
    throw new Error('Cannot copy the document reference. Allow clipboard access and try again.');
  }
  return reference;
}
