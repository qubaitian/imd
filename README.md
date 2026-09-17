# IMD — Interactive Markdown

IMD is a Markdown editor that runs on this computer.  
The browser shows GitHub-style documents.  
Svelte builds the interface.  
CodeMirror provides block editing and full-source editing.  
IPython runs the code.  

## Confirmed design

### Browser links

- On macOS, Cmd + click opens HTTP and HTTPS links in Google Chrome.  
- Links work in Markdown preview, block editors, Source view, code blocks, and output blocks.  
- IMD marks a browser link only when the text starts with `http://` or `https://`.  
- A name such as `README.md`, `app.py`, or `www.example.com` is not a browser link.  
- IMD uses macOS automation and needs no browser extension.  
- macOS can ask for permission to control Chrome on first use.  
- IMD searches all Chrome windows, including tabs that the user opens manually.  
- A match uses the protocol, host, and effective port.  
- Paths, query parameters, and fragments do not affect the match.  
- An omitted HTTP port means 80.  
- An omitted HTTPS port means 443.  
- `localhost` and `127.0.0.1` are separate hosts.  
- IMD selects the first matching tab in the first matching window, from front to back and left to right.  
- IMD brings the matching window to the front without changing or reloading its page.  
- If no tab matches, IMD opens and selects a new tab in the front Chrome window.  
- If Chrome has no window, IMD creates a window.  
- An automation failure shows an error in IMD.  
- Other operating systems and browsers do not support this operation.  

### Local path links

- Cmd + click opens absolute paths and relative paths in all browser link locations.  
- Relative paths use the session start directory, even after a kernel changes its working directory.  
- Paths can start with `./` or `../`, contain `/`, or name a file such as `README.md`.  
- A directory name without `/` needs a `./` prefix.  
- Put paths with spaces inside quotes, backticks, or a Markdown link.  
- Each file click adds a document panel at the right end of the current page.  
- All panels have equal width, with no limit on the panel count.  
- Repeated file clicks also add panels.  
- Panels for the same file share its document kernel.  
- Save conflicts keep the file unchanged and show an error.  
- Markdown files support editing and code execution.  
- Other UTF-8 text files show read-only text.  
- Binary files and missing paths show an error.  
- A directory click selects the most recently created live session with the same resolved start directory.  
- If no session matches, IMD runs `imd open` in that directory.  
- Open creates the temporary Markdown file through the existing session operation.  
- IMD opens the directory session in Chrome through the existing browser operation.  
- Directory clicks do not add document panels to the current page.  
- The CLI and Python session operations keep their existing names and arguments.  

### Session commands

- The CLI and Python API always expose the same session operation names, arguments, behavior, and information.  
- Both interfaces use the same implementation.  
- `imd open` and `imd.open()` create a new session in the current working directory.  
- Open accepts no file arguments.  
- Each open creates one empty Markdown file under `/tmp/<current absolute directory>/`.  
- Open creates missing temporary directories.  
- The file name uses local time, the process id, and a random suffix: `yyyy-MM-ddTHH-mm-ss-<pid>-<random>.md`.  
- Open never overwrites an existing file.  
- The operating system can remove files in `/tmp`.  
- The session stores its absolute start directory as `cwd`.  
- This value stays fixed when document code changes a kernel working directory.  
- Open selects a free port and starts a background service.  
- Open returns the shell without opening a browser.  
- Open prints `(http_address, cwd, file1, file2, ...)`.  
- The address includes the session access token.  
- File paths are absolute and follow the document order from left to right.  
- The output includes only the open files and has no empty file fields.  
- `imd list` prints all live sessions, one session per line.  
- An empty list prints no text.  
- `imd close <port>` stops the session at that port and keeps its files.  
- Close accepts a port from 1 through 65535.  
- Close does not accept a file path or URL.  
- Close prints no text on success and reports an error on failure.  
- The old command names and formats are not supported.  
- Session records live in `~/.imd/sessions.json`.  
- Each record stores the address, start directory, document paths, and process ID.  
- List and close remove records for processes that no longer run.  
- A live record from an earlier version has no start directory.  
- Close that session by port and open a new session before listing sessions.  
- Background service logs go to `/dev/null`.  
- Unix and macOS are supported.  
- `cli.py` handles commands.  
- `_server.py` runs the service without importing `cli.py`.  

### Python session API and completion

- Each kernel imports `imd` at startup.  
- `imd.open()` returns a `Session` object.  
- `imd.list()` returns a list of `Session` objects.  
- `imd.close(port)` stops the specified session, keeps its files, and returns `None`.  
- `Session.url` is the session address.  
- `Session.cwd` is the absolute start directory.  
- `Session.paths` is a tuple of absolute document paths in display order.  
- `Session.port` is the port from the session address.  
- API calls return data without printing it.  
- API failures raise exceptions.  
- A kernel cannot close its own session through the Python API.  
- The CLI or another session can close that session.  
- Code block editors and code regions in Source view request completion from their document kernel.  
- Typing requests completion asynchronously and does not block input.  
- The editor shows a menu when candidates exist.  
- `Ctrl+Space` requests completion manually.  
- When the menu is visible, `Tab` accepts the selected candidate.  
- When the menu is hidden, `Tab` does nothing.  
- `Tab` does not indent text.  
- A busy kernel returns no candidates without queuing the request.  
- Later input or a manual request can request completion again.  
- This change provides name completion.  
- Parameter hints and hover documentation are outside this change.  

### Save

- Save before code execution.  
- Save when the editor loses focus.  
- Save after the result is written to the document.  

### Execute

- `Shift + Enter` runs. `Enter` adds a line.  
- Every fenced code block can run, except `out`.  
- Language tags stay as written. An empty tag is allowed.  
- IMD does not use the language tag to decide if a block can run.  
- The user decides whether to run a block.  
- All runnable blocks in one document use the same IPython session.  
- automagic stays enabled.  
- Python variables, the working directory, and environment variables persist across blocks.  
- `cd` or `%cd` changes the working directory.  
- `env NAME=value` or `%env NAME=value` sets an environment variable.  
- `!command` runs an ordinary system command.  
- Text results go into the adjacent `out` block.  
- A later run replaces that `out` block.  
- Parsed block kinds are `markdown`, `code`, and `output`.  

### Delete blocks

- Each code block has a `Del` button beside `Run`.  
- Each `out` block has a `Del` button in its header.  
- Each `Del` button shows a small trash icon next to the `Del` text.  
- `Del` removes the complete `out` block.  
- `Del` on a code block removes that block and its adjacent `out` block.  
- All `Del` buttons in a document stay disabled while that document runs code.  
- Each deletion saves immediately.  
- Deletion does not open a confirmation dialog.  

### Live command output and input

- The adjacent `out` block shows output during execution.  
- Progress updates replace text at the cursor position.  
- `!command` accepts each key directly in the `out` terminal.  
- Space selects an item in a command menu.  
- Arrow keys move through a command menu.  
- Enter confirms a command menu selection.  
- Ctrl+C sends an interrupt to the command terminal.  
- Command input does not add a newline automatically.  
- Commands do not show a separate input field or Send button.  
- Python `input()` shows an input field only while it waits for a line.  
- The input field closes after the user submits the line.  
- A Stop button interrupts execution.  
- Stop kills the process group of a running command.  
- The document saves the final displayed text when execution ends.  
- Full-screen terminal programs are outside this design.  

Opening a document does not run code.  
Session state ends when the service stops.  
Image output, rich output, run-all, and reset are not in version 1.  
Code blocks use IPython syntax.  
`%%bash` and `!export` subprocess state does not write back to the IPython session.  

### Tooling

- Python package manager: uv.  
- Lockfile: `uv.lock` stays in the repository.  
- Dev dependencies: dependency group `dev`.  
- Python formatter: Ruff.  
- Python version: `requires-python >= 3.11`, no pinned `.python-version`.  
- Development start: `uv run imd open`.  
- Daily start: `uv tool install .`, then `imd open` from any directory.  
- A later `uv tool install` of another package with the same entry name replaces `imd`.  
- The Python package lives in `imd/` at the project root.  

## Install and start

Install [uv](https://docs.astral.sh/uv/).  
The development environment needs Python 3.11 or later.  
The frontend build needs Node.js 22.12 or later.  
Run these commands in the project directory.  

```sh
uv sync
npm --prefix web ci
npm --prefix web run build
uv run imd open
```

`uv sync` creates `.venv`, installs the package, and installs the `dev` group.  
Use `uv sync` before backend tests and browser e2e tests.  
`imd open` prints the address, start directory, and document paths, then returns the shell.  
Open the printed URL in the browser.  
The service listens only on `127.0.0.1`.  
The printed address includes the access credential for the current session.  
Use `imd close <port>` to stop one session.  

For daily use from any directory, install the tool once from the project directory.  

```sh
npm --prefix web run build
uv tool install .
```

Then start from any directory.  

```sh
imd open
imd list
imd close 12345
```

Use the port from the printed address in the close command.  
Each open creates a separate session with one temporary document.  
The initial IPython working directory is the start directory.  

## Use

Click a text block or a code block in the document to edit it.  
Click "Source" to edit the full Markdown.  
Press `Shift + Enter` in a code block to run the current block.  
You can also click "Run" in the top-right of the code block.  
In the source view, put the cursor in a code block and press `Shift + Enter`.  
`Enter` inserts a new line.  
The editor saves when it loses focus.  
A switch of the browser window or tab also triggers a save.  
`Ctrl + S` or `Cmd + S` triggers a save in the editor.  

Every fenced code block can run, except `out`.  
Language tags stay as written. An empty tag is allowed.  
IMD does not use the language tag to decide if a block can run.  
The user decides whether to run a block.  
All runnable blocks in one document use IPython syntax and share one session.  
Code blocks share Python variables, the working directory, and environment variables.  
`env NAME=value` sets an environment variable.  
`cd path` changes the working directory.  
Ordinary system commands use a `!` prefix.  
Multiline code blocks also support automagic.  
As in IPython, a Python variable with the same name can hide a magic command.  
Then use explicit `%cd` or `%env`.  
"Add a code block" inserts a `python` fence by default.  

````markdown
```python
value = 40
value + 2
```

```out
42
```

```shell
cd /tmp
env IMD_MESSAGE=hello
!echo "$IMD_MESSAGE"
```
````

The output includes standard output, standard error, and the text result of an expression.  
The text of an exception also shows in the `out` block.  
A later execution replaces the adjacent `out` block.  
Content in other positions stays the same.  
If the output contains backticks, IMD increases the fence length.  
Click the `out` terminal to send keys directly to a command.  
Use Space, arrow keys, and Enter as the command menu specifies.  
Python `input()` shows a separate input field.  
Type a response in that field and press Enter to submit the line.  
Click Stop to interrupt execution.  
Stop kills a running command process.  
If the browser disconnects, IMD interrupts execution and saves the final text.  
Local image paths are relative to the document directory.  
Local images must stay inside the document directory.  

If another program changes the file, IMD stops overwrite saves.  
Then click "Download current content" to keep the browser changes. Reload the document after that.  

## Example

Use the Python API in a code block.  
The kernel already imports `imd`.  
Other Python programs must first run `import imd`.  

```python
session = imd.open()
session.url
session.cwd
session.paths
imd.list()
imd.close(session.port)
```

The last call closes the new session and keeps its document.  
A kernel cannot close its own session through this API.  
Type `imd.` in a code editor to see completion candidates.  
Press `Tab` to accept the selected candidate.  
Without a completion menu, `Tab` does nothing.  

```sh
uv run imd open
```

## Tests

```sh
uv sync
uv run pytest -q
npm --prefix web run check
npm --prefix web run build
cd web
npx playwright install chromium
npm run test:e2e
```

Backend smoke tests start a real IPython kernel.  
Browser smoke tests use a temporary document.  
Playwright starts `tests/browser_server.py` with `.venv/bin/python`.  
The test server listens on `127.0.0.1:18741` and uses the token `browser-test`.  
The server removes the temporary directory when it stops.  
The tests do not execute code in user documents.  

The frontend build writes to `imd/static`.  
The Python wheel includes these static files.  
Build the frontend before you build the wheel.  
