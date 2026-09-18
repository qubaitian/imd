# IMD — Interactive Markdown

IMD is a Markdown editor with code execution on the computer that runs the service.  
The browser provides a GitHub-style preview, block editing, and full-source editing.  
Svelte provides the interface.  
CodeMirror provides the editors.  
Each document uses a persistent shell with a PTY.  

## Scope

IMD supports Unix and macOS.  
HTTP links and directory links use Google Chrome automation on macOS.  
These operations need no browser extension.  
Image output, rich output, run-all, reset, and full-screen terminal programs are outside version 1.  

## Session design

One operating system user shares one background service and one fixed HTTP port across all sessions.  
The first session starts the service.  
The last session close stops the service and releases the port.  
A port conflict reports an error.  
Each session has its own access token, fixed start directory, documents, and shells.  
Session numbers increase across service restarts.  
Opening a document does not execute code.  

### CLI and Python API

Both interfaces use the same implementation, operation names, arguments, behavior, and session information.  

| Operation | CLI | Python API | Result |
| --- | --- | --- | --- |
| Create a session | `imd open` | `imd.open()` | One session |
| List live sessions | `imd list` | `imd.list()` | All live sessions for the current user |
| Close one session | `imd close <number>` | `imd.close(number)` | Stop the session and keep its files |
| Close all sessions | `imd close` | `imd.close()` | Stop all sessions and keep their files |

Open accepts no arguments and uses the current working directory.  
Each open creates an empty Markdown file under `/tmp/<current absolute directory>/`.  
IMD creates missing directories and never overwrites an existing file.  
The file name uses local time, the process ID, and a random suffix: `yyyy-MM-ddTHH-mm-ss-<pid>-<random>.md`.  
The operating system can remove these temporary documents.  
Open returns control to the caller without opening a browser.  

The CLI prints `(http_address, cwd, file1, file2, ...)` for each session.  
The address includes the access token.  
File paths are absolute and follow panel order.  
An empty list and a successful close print no text.  
CLI failures report an error.  

The Python API returns a `Session` from open, a list of `Session` objects from list, and `None` from close.  
API calls print no text and raise exceptions on failure.  

| Session field | Meaning |
| --- | --- |
| `url` | Session address with its access token |
| `cwd` | Absolute start directory |
| `paths` | Tuple of absolute document paths in panel order |
| `number` | Positive integer from the URL path |
| `port` | Public URL port, or 80 for HTTP and 443 for HTTPS when absent |

Close accepts only an optional positive session number.  
A call from a document cannot close its own session by number through either interface.  
A call from outside that session can close it.  
A call without a number can close all sessions, including the caller's session.  
IMD closes the caller's session last, so that call might not return.  
Close attempts every selected session and reports any errors.  
An external close call waits for service shutdown when it closes the last session.  
Close with no number succeeds when no sessions exist and does not start the service.  

### Access and service state

Each session URL uses `/<number>/#token=<token>`.  
The page moves the token from the address bar into `sessionStorage` for that tab.  
Reloading the same tab keeps access.  
A new tab needs the full URL with the token.  
The service accepts any HTTP Host name.  
Local session operations use a Unix socket with access only for the current user.  

Session records live in `~/.imd/sessions.json`.  
Each record stores the number, address, start directory, document paths, and service process ID.  
List and close remove records for processes that no longer run.  
The `~/.imd` directory permits access only by the current user.  
Service logs go to `~/.imd/server.log`.  
Each service start replaces the log file.  

## Document design

### Panels and editing

Each file click adds a panel at the right end of the page, including repeated clicks on the same file.  
Panels have equal width, with no panel count limit or controls to close or resize them.  
Within a session, panels for the same file share one document and shell.  
Each panel keeps its own unsaved draft.  
Different documents have separate shells.  

Files with `.md` or `.markdown` suffixes support editing and execution.  
Other UTF-8 text files show read-only text with a Read-only label.  
Binary files and missing paths report an error.  

A Markdown panel shows the file name, Local badge, Document and Source controls, and save status.  
A narrow panel hides the Local badge.  
The bottom row shows the absolute file path and `Markdown · Shell`.  
A read-only panel has no Document or Source controls.  
The browser title lists the open file names, separated by ` | `, followed by ` · IMD`.  

Document view supports block editing and controls to add text or code.  
A new code block uses the `python` tag.  
Click, Enter, or Space starts an edit of a selected block.  
Source view edits the full Markdown document.  

| Control | Behavior |
| --- | --- |
| Enter in an editor | Add a line |
| Shift + Enter in a code block | Save and run that block |
| Shift + Enter in Source view | Run the code block at the cursor |
| Shift + Enter in a Markdown block editor | Save without execution |
| Ctrl + S or Cmd + S | Save |
| Tab in an editor | No action |

Editors show no completion menu.  

### Markdown and images

Preview supports tables, strikethrough, and task lists, but does not render raw HTML.  
Local image paths use the document directory and must stay inside that directory.  
Supported suffixes are `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.svg`, `.avif`, `.ico`, and `.bmp`.  
Images load only after the document opens.  
Image requests do not include the session token in the URL.  

### Save and conflicts

IMD saves before execution, after execution output, and before Cmd + click opens a link.  
IMD also saves when an editor loses focus or the user switches browser windows or tabs.  
User saves are refused while the document runs code.  
IMD blocks link clicks during execution and asks the user to wait.  
A failed save prevents the link from opening.  
Save keeps the original LF or CRLF line endings and file mode.  
Unsaved changes or a running block make the browser ask before the tab closes.  

A save fails if the file changes after the panel reads it.  
This rule applies to changes from another program or another panel.  
A conflict keeps the file unchanged and shows an error.  
Use Download current content to keep the draft, then reload the document.  

### Links

Cmd + click handles links in preview, block editors, Source view, code blocks, and output.  
Only text that starts with `http://` or `https://` is an HTTP link.  

HTTP links select a matching Chrome tab without changing or reloading its page.  
A match uses protocol, host, and effective port, with no host letter-case difference.  
The default ports are 80 for HTTP and 443 for HTTPS.  
Paths, query parameters, and fragments do not affect HTTP link matches.  
`localhost` and `127.0.0.1` are separate hosts.  
IMD searches all Chrome windows from front to back and tabs from left to right.  
IMD restores and selects the first matching window and tab.  
If no tab matches, IMD opens a tab in the front window or creates a window.  
Automation failures show an error.  
macOS can request permission to control Chrome on first use.  

Local links accept absolute and relative paths.  
Relative paths use the fixed session start directory, even after the shell changes directory.  
Paths can start with `./` or `../`, contain `/`, or name a file such as `README.md`.  
A directory name without `/` needs a `./` prefix.  
Paths with spaces need quotes, backticks, or a Markdown link.  
File links open panels as specified above.  

A directory link selects the newest live session with the same resolved start directory.  
If none exists, IMD uses the open operation in that directory.  
IMD opens the session in Chrome without adding a panel to the current page.  
Unlike HTTP link matches, directory session matches also use the URL path.  

## Execution design

### Shell and Python

The first execution starts the document shell in the session start directory.  
The shell must start within 30 seconds or report an error.  
IMD uses `$SHELL`, or the user's login shell if `$SHELL` is absent.  
The shell starts in interactive mode without login mode and loads its configuration.  
IMD requires a POSIX-compatible shell and rejects `fish`, `csh`, and `tcsh`.  
The shell keeps environment variables, aliases, functions, its working directory, and options between blocks.  
Shell state ends when the shell stops.  

| Language tag | Execution |
| --- | --- |
| No tag or `shell` | Source the block in the document shell |
| `python` | Run a new script with `python3` from the document shell |
| Any other tag, including `py` | Report an error and run nothing |

Language tags ignore letter case.  
Shell commands need no `!` prefix.  
Python inherits the shell's exported environment and working directory.  
Python keeps no state between blocks and prints no last expression value.  
Both standard output and standard error appear in the output region.  
Only one execution runs at a time in a document.  
Background jobs can continue after a block ends, with later output appearing in the next execution.  
Names that start with `__imd_` belong to IMD.  

### Output and input

During execution, the adjacent output region shows a terminal with 100 columns and 24 rows.  
The terminal sends each key to the PTY without adding a newline.  
Programs control Space, arrow keys, Enter, and input such as Python `input()`.  
Progress updates replace text at the cursor position.  
When execution ends, IMD saves the final text and renders it as Markdown without an exit code.  
An empty output region shows `(no output)`.  

Each output region uses a unique ID in two markers on separate lines:  

```markdown
<!-- imd:output:begin ID -->

Output content

<!-- imd:output:end ID -->
```

Preview hides the markers.  
Code blocks inside output support editing and execution.  
Their output stays inside the parent output region.  
Each run replaces the adjacent output region and all its nested content.  
The `out` tag has no special meaning and does not identify an output region.  

Code blocks and output regions have a Del control.  
Deleting code also removes its adjacent output region.  
Deleting output removes both markers and their content.  
Deletion saves immediately without a confirmation dialog.  
Delete controls stay disabled while the document runs code.  

### Stop and close

Stop and terminal Ctrl+C send an interrupt to the foreground process group.  
The shell keeps its state if it survives the interrupt.  
After Stop, Kill becomes available if execution continues.  
Kill stops the shell process group and saves `The shell stopped. The state is lost.` in the output.  
The next execution starts a new shell.  

A browser disconnect interrupts execution without killing the shell and saves the final text.  
A document close interrupts execution and waits up to two seconds before stopping the shell.  
Close releases the shell, its child processes, the PTY, and execution temporary files.  
Document files remain on disk.  

## Install and start

The project needs Python 3.11 or later, uv, and Node.js 22.12 or later for the frontend build.  
Install the tool from the project directory:  

```sh
uv tool install .
```

Each wheel build installs frontend dependencies and rebuilds the frontend with npm.  
The wheel includes the generated files in `imd/static`, which stays out of Git.  

Run from any directory:  

```sh
imd open
imd list
imd close 1
```

Open the printed URL in a browser.  
Use the actual session number from its URL path in the close command.  

Use the same operations from Python:  

```python
import imd

session = imd.open()
print(session.url, session.cwd, session.paths, session.number)
imd.close(session.number)
```

### Server configuration

Each open reads `~/.imd/config.py` with the current user's permissions.  
The file defines a Python dictionary named `config`.  
A missing file uses the defaults below.  
An invalid file reports its path and an error.  

```python
config = {
    "host": "0.0.0.0",
    "port": 8000,
}
```

`host` accepts an IPv4 or IPv6 listen address.  
`port` sets the fixed HTTP port.  
An optional `public_url` sets the printed HTTP or HTTPS origin, with an optional port and no path, query, or token.  
Without `public_url`, IMD builds an HTTP URL from `host` and `port`.  
For an HTTPS reverse proxy, use a configuration such as:  

```python
config = {
    "host": "127.0.0.1",
    "port": 8000,
    "public_url": "https://imd.example.com",
}
```

The proxy provides HTTPS and forwards requests to the listen address with their paths intact.  
Setting `public_url` does not configure the proxy.  
A running service keeps its initial settings.  
After a configuration change, run `imd close`, then `imd open`.  
List and close remain available if the configuration file contains an error.  

## Development

The project uses uv and keeps `uv.lock` in Git.  
`uv sync` installs the package in editable mode with the `dev` dependency group.  
Editable installs need a separate frontend build:  

```sh
uv sync
npm --prefix web ci
npm --prefix web run build
uv run imd open
```

Run the checks from the project directory after this setup:  

```sh
uv run pytest -q
npm --prefix web run check
cd web
npx playwright install chromium
npm run test:e2e
```

Browser tests use `.venv/bin/python` and temporary documents.  
Tests do not execute code in user documents.  
