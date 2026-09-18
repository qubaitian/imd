# IMD — Interactive Markdown

IMD is a Markdown editor that runs on this computer.  
The browser shows GitHub-style documents.  
Svelte builds the interface.  
CodeMirror provides block editing and full-source editing.  
A persistent shell runs the code.  

## Confirmed design

### Document layout

- One top row shows the file name, Document and Source controls, and save status in that order.  
- The top row has a height of 48 pixels.  
- The top row has no IMD logo or run shortcut hint.  
- The document has no footer with editing hints or execution time.  
- Code blocks keep their Run controls.  

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
- Relative paths use the session start directory, even after a shell changes its working directory.  
- Paths can start with `./` or `../`, contain `/`, or name a file such as `README.md`.  
- A directory name without `/` needs a `./` prefix.  
- Put paths with spaces inside quotes, backticks, or a Markdown link.  
- Each file click adds a document panel at the right end of the current page.  
- All panels have equal width, with no limit on the panel count.  
- Repeated file clicks also add panels.  
- Panels for the same file share its document shell.  
- Save conflicts keep the file unchanged and show an error.  
- Markdown files support editing and code execution.  
- Other UTF-8 text files show read-only text.  
- Binary files and missing paths show an error.  
- A directory click selects the most recently created live session with the same resolved start directory.  
- If no session matches, IMD runs `imd open` in that directory.  
- Open creates the temporary Markdown file through the existing session operation.  
- IMD opens the directory session in Chrome through the existing browser operation.  
- Directory sessions match the URL path as well as the protocol, host, and port.  
- Directory clicks do not add document panels to the current page.  
- The CLI and Python session operations use the same names and arguments.  

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
- This value stays fixed when document code changes the shell working directory.  
- All sessions for one operating system user share one background service and one fixed HTTP port.  
- The first open starts the service.  
- The default listen address is `0.0.0.0:8000`.  
- The default public URL is `http://0.0.0.0:8000`.  
- Each session URL uses `/<number>/#token=<token>`.  
- Session numbers increase across service restarts.  
- Each session keeps its own access token, start directory, documents, and shells.  
- A port conflict reports an error instead of selecting another port.  
- The service accepts any HTTP Host name.  
- Open returns the shell without opening a browser.  
- Open prints `(http_address, cwd, file1, file2, ...)`.  
- The address includes the session access token.  
- File paths are absolute and follow the document order from left to right.  
- The output includes only the open files and has no empty file fields.  
- `imd list` prints all live sessions, one session per line.  
- An empty list prints no text.  
- `imd close <number>` stops one session and keeps its files.  
- `imd close` stops all sessions for the current user across all start directories.  
- Close without a number stops running code, keeps document files, and stops the shared service.  
- Close without a number succeeds when no sessions exist and does not start the service.  
- If one session fails to close, close attempts the remaining sessions and reports the errors.  
- An external close call waits for the shared service to stop before it reports success.  
- Close accepts an optional positive integer session number from the URL path.  
- Closing the last session stops the shared service and releases the port.  
- Close does not accept a file path or URL.  
- Close prints no text on success and reports an error on failure.  
- The old command names and formats are not supported.  
- Session records live in `~/.imd/sessions.json`.  
- Each record stores the number, address, start directory, document paths, and shared service process ID.  
- List and close remove records for processes that no longer run.  
- Stop sessions from an earlier version before upgrading.  
- Use the earlier version of `imd close <port>` to stop those sessions.  
- Background service logs go to `~/.imd/server.log`.  
- Local session operations use a Unix socket that permits access only by the current user.  
- Unix and macOS are supported.  
- `cli.py` handles commands.  
- `_server.py` runs the service without importing `cli.py`.  

### Python session API

- A Python block imports `imd` before it uses the session API.  
- A shell block uses the `imd` command.  
- `imd.open()` returns a `Session` object.  
- `imd.list()` returns a list of `Session` objects.  
- `imd.close(number)` stops the specified session, keeps its files, and returns `None`.  
- `imd.close()` stops all sessions with the same behavior as `imd close`.  
- `Session.url` is the session address.  
- `Session.cwd` is the absolute start directory.  
- `Session.paths` is a tuple of absolute document paths in display order.  
- `Session.number` is the session number from the URL path.  
- `Session.port` is the public port from the session address.  
- An omitted HTTPS port means 443.  
- An omitted HTTP port means 80.  
- API calls return data without printing it.  
- API failures raise exceptions.  
- A document cannot close its own session through `imd.close(number)`.  
- The shell exports `IMD_SESSION_TOKEN`, so the API knows the caller session.  
- The CLI or another session can close that session.  
- A document can close all sessions through `imd.close()` or `imd close`.  
- Close without a number closes all other sessions before it closes the caller's session.  
- A call from that session does not need to return a value.  
- IMD shows no completion menu.  
- `Tab` does nothing and does not indent text.  

### Save

- Save before code execution.  
- Save when the editor loses focus.  
- Save after the result is written to the document.  

### Execute

- `Shift + Enter` runs. `Enter` adds a line.  
- Each document keeps one persistent shell with a PTY.  
- Documents do not share a shell.  
- Panels for the same file share the shell of that document.  
- IMD starts the shell at the first execution. Opening a document starts no shell.  
- IMD uses `$SHELL`. Without `$SHELL`, IMD uses the login shell of the user.  
- The shell starts in interactive mode without login mode, so the shell loads its own configuration.  
- IMD needs a POSIX shell. A `fish`, `csh`, or `tcsh` value in `$SHELL` reports an error.  
- After start, IMD turns off the line editor. zsh uses `unsetopt zle`. bash uses `set +o emacs; set +o vi`.  
- A code block with no language tag or with the `shell` tag runs in the shell. The command needs no `!` prefix.  
- A code block with the `python` tag runs as a Python script.  
- Every other language tag reports an error and runs nothing.  
- Environment variables, aliases, functions, the working directory, and shell options stay between blocks.  
- IMD writes each block into a private temporary directory of the document, one file for each execution.  
- A shell block runs with `.`, so the block changes the state of the shell.  
- A Python block runs with `python3`, so the interpreter comes from the current shell.  
- A Python block reads the exported environment variables and the working directory of the shell.  
- A Python block keeps no state between blocks. IMD runs no Python REPL.  
- A Python block writes output with `print` and with standard error. IMD prints no last expression value.  
- IMD deletes the block file when the execution ends.  
- Only one execution runs at a time in one document.  
- The output region shows no exit code.  
- Background jobs continue after a block ends. Their later output appears in the block that runs next.  
- Text results go into the adjacent Markdown output region.  
- A later run replaces that output region and all its nested content.  
- Parsed block kinds are `markdown`, `code`, and `output`.  

### Execution protocol

- At start, IMD writes `helper.sh` into the temporary directory and sources that file.  
- `helper.sh` defines `__imd_marker` and `__imd_run`.  
- Each execution sends one short line: `__imd_run <id> <shell|python> <file>`.  
- A short line keeps the shell reader and the terminal line limit safe.  
- `__imd_marker` prints `ESC ] imd ; <id> ; b ; BEL` before the block.  
- `__imd_marker` prints `ESC ] imd ; <id> ; e ; <status> BEL` after the block.  
- IMD keeps the bytes between the two markers of the current id.  
- The markers hide the prompt, the echo of the sent line, and shell plugin output.  
- An OSC marker stays invisible in a terminal.  
- An `INT` trap prints the end marker when an interrupt stops the block, so an interrupt also ends the execution.  
- `__imd_run` sources the block, so `local` works, `$1` is empty, and a top-level `return` ends the execution.  
- Names that start with `__imd_` belong to IMD.  

### Stop and restart

- A Stop click sends Ctrl+C to the PTY.  
- The terminal sends SIGINT to the foreground process group.  
- The shell stays alive and keeps its state.  
- After the interrupt, the button shows `Kill`.  
- A Kill click sends SIGKILL to the process group of the shell.  
- The output region gets the line `The shell stopped. The state is lost.` and the document saves that line.  
- The next execution starts a new shell.  
- A browser disconnect sends Ctrl+C. A disconnect never kills the shell.  
- A document close sends Ctrl+C, waits at most 2 seconds for the command to end, and then stops the shell.  
- The wait gives a running program the time to clean up, so the document saves the real output.  
- A document close stops the shell, its child processes, the PTY, and the temporary files.  

### Markdown output

- Each output region starts with `<!-- imd:output:begin ID -->`.  
- Each output region ends with `<!-- imd:output:end ID -->`.  
- Each marker occupies its own line.  
- Each generated output region has a unique ID.  
- Both markers use the same ID.  
- Markers stay hidden in Markdown preview.  
- Output renders as Markdown after execution ends.  
- During execution, output uses the existing terminal display and input controls.  
- Code blocks inside output support editing and execution.  
- Each execution inserts a marked output region after its code block.  
- Output from a code block inside output stays inside the parent output region.  
- A repeat execution replaces the adjacent output region and all its nested content.  
- Output deletion removes both markers and all content between them.  
- Code deletion removes the code block and its adjacent output region.  
- The `out` language tag has no special meaning.  
- IMD does not read or convert old `out` fences as output.  

### Delete blocks

- Each code block has a `Del` button beside `Run`.  
- Each output region has a `Del` button in its header.  
- Each `Del` button shows a small trash icon next to the `Del` text.  
- `Del` removes the complete output region.  
- `Del` on a code block removes that block and its adjacent output region.  
- All `Del` buttons in a document stay disabled while that document runs code.  
- Each deletion saves immediately.  
- Deletion does not open a confirmation dialog.  

### Live output and input

- Every execution shows a terminal in the adjacent output region.  
- The terminal shows output while the block runs.  
- Progress updates replace text at the cursor position.  
- Each key goes to the PTY without change.  
- Space, arrow keys, and Enter work as the running program defines.  
- Ctrl+C in the terminal interrupts, like a Stop click.  
- Key input adds no newline automatically.  
- There is no separate input field and no Send button.  
- Python `input()` reads the terminal like any other program.  
- The terminal keeps 100 columns and 24 rows. The size does not change.  
- The document saves the final text when the execution ends.  
- The output region shows that text as Markdown after the execution.  
- Full-screen terminal programs are outside this design.  

Opening a document does not run code.  
Shell state ends when the service stops.  
Image output, rich output, run-all, and reset are not in version 1.  

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
- `hatch_build.py` is the wheel build hook.  
- A wheel build runs `npm --prefix web ci` and `npm --prefix web run build`.  
- `uv tool install .`, `uv build`, and `uv tool install git+...` build a wheel, so they run npm.  
- Each wheel build rebuilds the frontend. Existing `imd/static` does not skip npm.  
- `uv sync` uses an editable install and does not run npm.  
- Missing npm fails the wheel build. The error asks for Node.js 22.12 or later.  
- `imd/static` stays out of git. The wheel includes these files as hatch artifacts.  
- Development with `uv run imd open` still needs a frontend build first, or use `uv tool install .`.  

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
The service listens on `0.0.0.0:8000` by default.  
All sessions share that port.  
The printed address includes the access credential for the current session.  
Use `imd close <number>` to stop one session.  
Use `imd close` to stop all sessions and the shared service.  

For daily use from any directory, install the tool once from the project directory.  

```sh
uv tool install .
```

The wheel build runs npm.  
Node.js 22.12 or later must be available.  

Then start from any directory.  

```sh
imd open
imd list
imd close 1
```

Use the session number from the printed URL path in the close command.  
Each open creates a separate session with one temporary document.  
The shell of each document starts in the start directory.  

### Server configuration

IMD reads `~/.imd/config.py` on each open.  
The path uses the current user's home directory, independent of the working directory.  
For `root`, the path is `/root/.imd/config.py`.  
The file defines a dictionary named `config`.  
IMD uses this code to read the file:  

```python
import runpy
from pathlib import Path

config_path = Path.home() / ".imd" / "config.py"
config = runpy.run_path(str(config_path))["config"]
```

The file runs as Python code with the current user's permissions.  
A missing file uses the default settings.  
An invalid file reports its path and an error.  

Create `~/.imd/config.py` for a server behind an HTTPS reverse proxy:  

```python
config = {
    "host": "127.0.0.1",
    "port": 8000,
    "public_url": "https://qubaitian.duckdns.org",
}
```

- `host` sets the listen address.  
- `port` sets the fixed HTTP port.  
- `public_url` sets the address that IMD prints.  
- `public_url` accepts an HTTP or HTTPS origin, with an optional port.  
- The URL must not contain a path, query, or token.  
- If `public_url` is absent, IMD builds an HTTP URL from `host` and `port`.  

Configure the reverse proxy to send requests for this domain to `http://127.0.0.1:8000`.  
The reverse proxy preserves each request path, including the session number.  
The reverse proxy provides the TLS certificate and HTTPS connection.  
Setting `public_url` does not install or configure a reverse proxy.  

For direct HTTP access, use this configuration:  

```python
config = {
    "host": "0.0.0.0",
    "port": 8000,
    "public_url": "http://qubaitian.duckdns.org:8000",
}
```

Direct access requires the server firewall to permit the configured port.  
The CLI and Python API use the same configuration.  
A running service keeps its initial settings.  
After changing settings, run `imd close`, then run `imd open`.  
List and close remain available if the configuration file contains an error.  

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

A block with no language tag or with the `shell` tag runs in the document shell.  
A block with the `python` tag runs as a Python script.  
Every other language tag reports an error.  
The blocks of one document share one shell.  
Environment variables, aliases, functions, the working directory, and shell options stay between blocks.  
A command needs no `!` prefix.  
A Python block starts a new Python process each time and keeps no variables.  
"Add a code block" inserts a `python` fence by default.  

````markdown
```shell
export IMD_MESSAGE=hello
cd /tmp
```

<!-- imd:output:begin a1b2c3 -->

<!-- imd:output:end a1b2c3 -->

```python
import os

print(os.environ["IMD_MESSAGE"], os.getcwd())
```

<!-- imd:output:begin d4e5f6 -->

hello /tmp

<!-- imd:output:end d4e5f6 -->
````

The output includes standard output and standard error.  
The text of an exception also shows in the output region.  
A later execution replaces the adjacent output region.  
Content in other positions stays the same.  
Click the terminal to send keys directly to the running program.  
Use Space, arrow keys, and Enter as that program defines.  
Python `input()` reads the same terminal.  
Click Stop to interrupt the command with Ctrl+C.  
The shell keeps its state after an interrupt.  
Click Kill to stop a command that ignores Ctrl+C.  
Kill stops the shell, and the next run starts a new shell without the old state.  
If the browser disconnects, IMD interrupts the command and saves the final text.  
Local image paths are relative to the document directory.  
Local images must stay inside the document directory.  

If another program changes the file, IMD stops overwrite saves.  
Then click "Download current content" to keep the browser changes. Reload the document after that.  

## Example

Use the Python API in a `python` block.  

```python
import imd

session = imd.open()
print(session.url, session.cwd, session.paths, session.number)
print(imd.list())
imd.close(session.number)
```

The last call closes the new session and keeps its document.  
A document cannot close its own session through this API.  
A shell block uses the command line for the same operations.  

```shell
imd open
imd list
```

```sh
uv run imd open
```

## Tests

The test suite checks configuration, shared sessions, the document shell, document execution, browser behavior, and the wheel build hook.  
The shell tests use the public interface of `imd/shell.py`.  
They check one command, state between blocks, a Python block, the Python environment, an unknown language tag, an interrupt, a kill, a close, and terminal keys.  
The backend test reads a document, saves a code block, runs `echo`, and checks the saved result.  
The browser test opens a document, runs one code block, and checks the displayed result.  
The wheel-hook test checks that a wheel build runs npm and that an editable install skips npm.  
The test suite keeps the test server and the tools that these tests need.  

```sh
uv sync
uv run pytest -q
npm --prefix web run check
npm --prefix web run build
cd web
npx playwright install chromium
npm run test:e2e
```

The backend smoke test starts a real shell.  
The browser smoke test uses a temporary document.  
Playwright starts `tests/browser_server.py` with `.venv/bin/python`.  
The test server listens on `127.0.0.1:18741` and uses the token `browser-test`.  
The server removes the temporary directory when it stops.  
The tests do not execute code in user documents.  

The frontend build writes to `imd/static`.  
The Python wheel includes these static files.  
A wheel build runs `npm ci` and `npm run build`.  
Do not run npm by hand before `uv tool install .` or `uv build`.  
