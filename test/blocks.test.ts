import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  addCodeBlock,
  deleteBlock,
  deleteOutput,
  findCodeBlocks,
  setCode,
  setOutput,
  splitSegments,
} from '../src/shared/blocks.ts';

const fence = '```';

test('it finds fenced code blocks with their code and info', () => {
  const md = `# Title\n\n${fence}sh\nls\npwd\n${fence}\n\ntext\n\n${fence}sh md\necho '# hi'\n${fence}\n`;
  const blocks = findCodeBlocks(md);
  assert.equal(blocks.length, 2);
  assert.equal(blocks[0].code, 'ls\npwd');
  assert.equal(blocks[0].markdown, false);
  assert.equal(md.slice(blocks[0].start, blocks[0].end), `${fence}sh\nls\npwd\n${fence}`);
  assert.equal(blocks[1].code, "echo '# hi'");
  assert.equal(blocks[1].markdown, true);
});

test('only a later word md makes Markdown output', () => {
  const [plain, markdownLang] = findCodeBlocks(`${fence}\nls\n${fence}\n\n${fence}md\n# x\n${fence}\n`);
  assert.equal(plain.markdown, false);
  assert.equal(markdownLang.markdown, false);
});

test('an agent block makes Markdown output', () => {
  const md = `${fence}codex\nhi\n${fence}\n\n${fence}sh\nls\n${fence}\n`;
  assert.deepEqual(
    findCodeBlocks(md, ['codex']).map(block => block.markdown),
    [true, false],
  );
  assert.equal(findCodeBlocks(md)[0].markdown, false);
  assert.match(setOutput(md, 0, '# Answer', ['codex']), /-->\n\n# Answer\n\n<!--/);
  const segments = splitSegments(md, ['codex']);
  assert.equal(segments[0].kind === 'code' && segments[0].block.markdown, true);
});

test('it ignores indented code and code inside lists', () => {
  assert.deepEqual(findCodeBlocks('    ls\n\n- item\n\n  ```\n  ls\n  ```\n'), []);
});

test('setOutput adds a txt output block right after the code block', () => {
  const md = `${fence}\nls\n${fence}\n\nafter\n`;
  const next = setOutput(md, 0, 'a.md\nb.md\n');
  assert.match(
    next,
    /^```\nls\n```\n\n<!-- imd:output:begin (\w+) -->\n```txt\na\.md\nb\.md\n```\n<!-- imd:output:end \1 -->\n\nafter\n$/,
  );
  const [block] = findCodeBlocks(next);
  assert.equal(block.output?.text, 'a.md\nb.md');
  assert.equal(findCodeBlocks(next).length, 1);
});

test('setOutput adds raw Markdown for a block with the word md', () => {
  const next = setOutput(`${fence}sh md\necho x\n${fence}\n`, 0, '# Hi\n\n- one\n');
  assert.match(
    next,
    /^```sh md\necho x\n```\n\n<!-- imd:output:begin (\w+) -->\n\n# Hi\n\n- one\n\n<!-- imd:output:end \1 -->\n$/,
  );
  assert.equal(findCodeBlocks(next)[0].output?.text, '# Hi\n\n- one');
});

test('setOutput replaces the old output and keeps its ID', () => {
  const first = setOutput(`${fence}\nls\n${fence}\n\nafter\n`, 0, 'old');
  const id = findCodeBlocks(first)[0].output?.id;
  const second = setOutput(first, 0, 'new');
  assert.equal(second, first.replace('old', 'new'));
  assert.equal(findCodeBlocks(second)[0].output?.id, id);
});

test('setOutput makes the txt fence longer than any backticks in the output', () => {
  const next = setOutput(`${fence}\ncat a.md\n${fence}\n`, 0, '```js\nx\n```');
  assert.ok(next.includes('\n````txt\n```js\nx\n```\n````\n'));
  const blocks = findCodeBlocks(next);
  assert.equal(blocks.length, 1);
  assert.equal(blocks[0].output?.text, '```js\nx\n```');
});

test('Markdown output contains runnable code blocks at any depth', () => {
  const root = setOutput(`${fence}sh md\necho root\n${fence}\n`, 0, 'before\n\n```sh md\necho child\n```\n\nafter');
  assert.deepEqual(
    findCodeBlocks(root).map(block => block.code),
    ['echo root', 'echo child'],
  );
  assert.deepEqual(
    splitSegments(root).map(segment => segment.kind),
    ['code', 'markdown'],
  );
  assert.deepEqual(
    splitSegments(root, [], 0).map(segment => segment.kind),
    ['markdown', 'code', 'markdown'],
  );

  const child = setOutput(root, 1, '```sh\necho grandchild\n```');
  assert.deepEqual(
    findCodeBlocks(child).map(block => block.code),
    ['echo root', 'echo child', 'echo grandchild'],
  );
  assert.deepEqual(
    splitSegments(child, [], 1).map(segment => segment.kind),
    ['code', 'markdown'],
  );
  assert.equal(findCodeBlocks(child)[0].output?.text.includes('echo grandchild'), true);

  const edited = setCode(child, 2, 'pwd');
  assert.equal(findCodeBlocks(edited)[2].code, 'pwd');
  assert.deepEqual(
    findCodeBlocks(deleteBlock(edited, 2)).map(block => block.code),
    ['echo root', 'echo child'],
  );
  assert.deepEqual(
    findCodeBlocks(deleteOutput(child, 1)).map(block => block.code),
    ['echo root', 'echo child'],
  );
  assert.deepEqual(
    findCodeBlocks(setOutput(child, 0, 'replacement')).map(block => block.code),
    ['echo root'],
  );
});

test('txt output stays literal even when it contains a code fence', () => {
  const md = setOutput(`${fence}sh\necho root\n${fence}\n`, 0, '```sh\necho example\n```');
  assert.deepEqual(
    findCodeBlocks(md).map(block => block.code),
    ['echo root'],
  );
});

test('a code block inside agent output can be edited and removed', () => {
  const agents = ['codex'];
  const md = setOutput(`${fence}codex\nwrite a command\n${fence}\n`, 0, '```sh\necho first\n```', agents);
  assert.deepEqual(
    findCodeBlocks(md, agents).map(block => block.code),
    ['write a command', 'echo first'],
  );
  const edited = setCode(md, 1, 'echo second', agents);
  assert.equal(findCodeBlocks(edited, agents)[1].code, 'echo second');
  assert.deepEqual(
    findCodeBlocks(deleteBlock(edited, 1, agents), agents).map(block => block.code),
    ['write a command'],
  );
});

test('an output block that is not right after a code block is not linked', () => {
  const md = `${fence}\nls\n${fence}\n\ntext\n\n<!-- imd:output:begin x -->\n\nhi\n\n<!-- imd:output:end x -->\n`;
  assert.equal(findCodeBlocks(md)[0].output, undefined);
});

test('deleteOutput removes only the output block', () => {
  const md = `a\n\n${fence}\nls\n${fence}\n\nb\n`;
  assert.equal(deleteOutput(setOutput(md, 0, 'x'), 0), md);
});

test('deleteBlock removes the code block and its output', () => {
  const md = `a\n\n${fence}\nls\n${fence}\n\nb\n`;
  assert.equal(deleteBlock(md, 0), 'a\n\nb\n');
  assert.equal(deleteBlock(setOutput(md, 0, 'x'), 0), 'a\n\nb\n');
  assert.equal(deleteBlock(`a\n\n${fence}\nls\n${fence}\n`, 0), 'a\n');
});

test('setCode replaces the code and keeps the fence, info, and output', () => {
  const md = setOutput(`a\n\n${fence}sh md\nls\n${fence}\n\nb\n`, 0, 'x');
  const next = setCode(md, 0, 'pwd\necho hi');
  assert.equal(next, md.replace('\nls\n', '\npwd\necho hi\n'));
  assert.equal(findCodeBlocks(next)[0].code, 'pwd\necho hi');
  assert.equal(findCodeBlocks(next)[0].output?.text, 'x');
});

test('setCode handles empty code and code with backticks', () => {
  assert.equal(setCode(`${fence}sh\nls\n${fence}\n`, 0, ''), `${fence}sh\n${fence}\n`);
  const next = setCode(`${fence}sh\nls\n${fence}\n`, 0, "cat <<'EOF'\n```\nEOF");
  assert.equal(findCodeBlocks(next)[0].code, "cat <<'EOF'\n```\nEOF");
});

test('addCodeBlock adds an empty sh block at the end', () => {
  assert.equal(addCodeBlock(''), `${fence}sh\n${fence}\n`);
  assert.equal(addCodeBlock('# A\n'), `# A\n\n${fence}sh\n${fence}\n`);
  assert.equal(addCodeBlock('# A\n\n\n'), `# A\n\n${fence}sh\n${fence}\n`);
  assert.equal(findCodeBlocks(addCodeBlock('# A')).length, 1);
});

test('splitSegments splits Markdown parts from code blocks and hides output blocks', () => {
  const md = setOutput(`# A\n\n${fence}\nls\n${fence}\n\nB\n`, 0, 'x');
  const segments = splitSegments(md);
  assert.deepEqual(
    segments.map(segment => segment.kind),
    ['markdown', 'code', 'markdown'],
  );
  assert.equal(segments[0].kind === 'markdown' && segments[0].text, '# A\n\n');
  assert.equal(segments[1].kind === 'code' && segments[1].block.output?.text, 'x');
  assert.equal(segments[2].kind === 'markdown' && segments[2].text, '\n\nB\n');
});
