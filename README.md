# IMD — Interactive Markdown

IMD is a local Markdown editor with code execution in the browser.  

## TERM

**IMD service**: The local Python process available at `http://localhost:8000`.  
**Frontend**: The HTML, JavaScript, and CSS files for the browser editor.  
**Service control**: A private local socket for stopping the IMD service.  
**Restart process**: An independent Python process for the next IMD service.  
**Service log**: A local file containing the IMD service startup and runtime messages.  
**Workspace**: An existing local directory identified by the absolute path in an IMD service URL.  
**Document**: A Markdown file inside the workspace.  
**Default document**: The document named `imd.md` at the workspace root.  
**Editor**: The text area containing a document's Markdown source in Edit or Split view.  
**Selection**: A nonempty range of text in the editor.  
**Document reference**: Plain text in the form `@/absolute/document/path.md:start-end` with inclusive source line numbers starting at 1.  
**Code block**: A fenced section of a document with a language label.  
**Executable block**: A code block with the label `xonsh`, `shell`, `sh`, `py`, or `python`.  
**Session**: A persistent xonsh process for one document, with its own working directory, environment, and Python variables.  
**Run**: One execution of an executable block inside its document's session.  
**Output marker**: A unique hexadecimal identifier in a Markdown comment after an executable block.  
**Output block**: A `txt` code block after an output marker containing the latest run's plain terminal output.  
**Console**: The temporary xterm view inside an output block during a run.  
**Terminal host**: The container without padding inside a console that defines the terminal screen's available space.  
**IMD**: A browser editor for workspace documents with executable blocks and output blocks.  

## DESIGN

The browser connects to the IMD service.  
`imd` starts the IMD service on port 8000 when it is stopped.  
`imd` restarts the IMD service when it is running.  
The restart process starts outside the document session before stopping the old service.  
The IMD service runs in the background after the command ends.  
Existing browser pages reconnect automatically after a restart.  
The command does not open a new browser tab.  
Restarting the service ends all sessions and clears their state.  
A directory URL opens the default document and creates an empty file if it is missing.  
An existing default document keeps its content.  
Different directory URLs select different workspaces in the same service.  
A missing directory returns an error.  
Each document has one session shared by all browser tabs that open that document.  
Different documents have separate sessions.  
All executable blocks use xonsh syntax, regardless of their language label.  
Runs in one session execute in order.  
A session starts in the document's directory.  
The session remains available after a browser refresh.  
Resetting a session clears its state.  
Stopping the service ends all sessions.  

The editor opens and saves Markdown files in the workspace.  
The preview has a Run button for each executable block.  
Each executable block has an output marker and an output block after its first run.  
The output block contains a console while its run is active.  
The console supports live output, keyboard input, resizing, interruption, and full-screen programs such as Vim.  
After the run, the output block contains plain text from the normal terminal screen and scrollback.  
The alternate terminal screen used by Vim is not part of the saved output.  
Another run replaces the same output block and keeps its output marker.  
The service automatically saves output when the run ends, even if the browser disconnects.  
The editor automatically saves changes after a short pause.  
`Cmd+L` copies a document reference for the selection when the browser passes the shortcut to the editor.  
The document reference uses the editor's current source, including unsaved changes.  
An end position at the start of the next line excludes that line.  
An empty selection leaves the clipboard unchanged.  
Copying shows a confirmation or an error without changing the selection.  
Output updates preserve other changes already saved in the document.  
Conflicting edits remain in the editor with a visible error.  

## ADR

### Document reference in Chrome

Use the editor's selection offsets instead of preview text because the editor contains the document's source lines.  
Use the browser Clipboard API instead of a service endpoint because copying is a local browser action.  
Keep the browser editor instead of adding a desktop window, as requested.  
Handle `Cmd+L` on the editor and cancel its default action only for a selection.  
A real Chrome check on macOS copied the selected source lines without changing browser or system settings.  
Use this existing key event behavior instead of requiring an extension or changing the address bar shortcut across Chrome.  
Other browser environments may reserve this shortcut before the editor receives it.  

### Directory URL and default document

Use `imd` instead of startup parameters for a fixed workspace.  
Use an absolute directory path in the URL instead of `--root` so one service can open several workspaces.  
Open `imd.md` instead of a previously selected document because the directory URL has one predictable document.  
Create the file only if it is missing so opening a URL preserves existing notes.  
Pass the workspace with each API request and session connection so browser tabs use their own directories.  
Keep document access inside its workspace and keep browser connections on the same local origin.  

### Frontend in the installation package

Include the built frontend in the Python wheel under `imd/static`.  
Read the bundled files after installation instead of expecting a repository beside the installed Python package.  
Keep the repository build directory as a fallback for development.  
Use Hatchling force-include instead of a separate frontend installation so `uv tool install --reinstall .` installs the complete editor.  
Build the frontend before building or installing the Python package.  

### Service control

Use a private Unix socket instead of finding and killing the process on port 8000.  
Another program may own that port.  
Use a file lock instead of a saved process identifier because an identifier may later belong to another process.  
Ask Uvicorn to stop so its normal shutdown closes sessions and releases the service control.  
Keep the service control in `$XDG_STATE_HOME/imd`, or `~/.local/state/imd` when that variable is absent.  

### Restart from a document session

Use one `imd` command instead of separate open and close commands.  
Start an independent restart process before stopping the old IMD service.  
A command inside a document session ends when that service stops.  
Use Python subprocess creation with a new operating system session and separate input and output instead of shell background execution.  
Shell background execution can keep the command inside the document session process group or attached to its terminal.  
Keep the restart process as the new service instead of adding a permanent supervisor.  
Use a file lock to serialize restarts so simultaneous commands cannot start competing services.  
Use a pipe to report service readiness or startup failure to an external terminal.  
A closed pipe from an ended document session does not stop the restart process.  
Write detached service messages to the service log because the original console may disappear.  
Keep the existing browser reconnect logic instead of opening a new tab or refreshing the page.  
An automatic refresh can lose unsaved edits.  

### Svelte and xterm

Use Svelte for a small browser bundle and a simple editor page.  
Use xterm for terminal output and keyboard input because command output can contain terminal control sequences.  
A plain text output view would lose terminal interaction.  

### uv, Python, and xonsh

Use uv to manage Python dependencies and commands.  
Use its dependency lock and startup command instead of separate pip and virtual environment steps.  
Use one persistent xonsh process per document instead of starting an interpreter for each block.  
A persistent process preserves directory changes, environment changes, and Python variables.  
Run every supported language label through xonsh instead of separate shell and Python interpreters.  
Separate interpreters would split the document's state.  

### Local service and process boundary

Use FastAPI for the file API and the session WebSocket.  
FastAPI keeps HTTP and WebSocket handling in one async service.  
A separate socket service would split session lifecycle management.  
Use a pseudo-terminal for session input and output.  
Use a separate control channel for run completion because command output can contain arbitrary text.  
Keep each session in a separate process because xonsh has process-wide state.  
Bind the service to the loopback interface and require a same-origin browser connection.  
Executable blocks have the same permissions as the local service.  

### Markdown preview

Use markdown-it for its fenced code renderer and support for nested Markdown blocks.  
Finding code blocks with text patterns would lose Markdown structure.  
Disable raw HTML and sanitize the preview with DOMPurify because documents are untrusted browser content.  
Use Vitest because it uses the frontend's Vite module pipeline.  
Disable the xonsh pytest plugin because these tests use the session interface instead of xonsh test files.  

### Output inside Markdown

Use a Markdown comment and a `txt` fence instead of a separate result file.  
A document remains readable in other Markdown tools.  
Use a stable output marker instead of a code block's position because edits can move code blocks.  
Use xterm during a run because a text fence alone cannot handle cursor movement or Vim.  
Use a terminal parser in the service to save plain output instead of terminal control sequences.  
Use pyte for terminal state instead of removing escape codes with text patterns.  
Text patterns cannot preserve cursor edits or restore the normal screen after Vim.  
Use morphdom to update the preview while preserving mounted output blocks.  
Replacing the preview HTML during a run would destroy the active xterm.  
Use a terminal host without padding because xterm's FitAddon counts its parent container's padding as available screen space.  
Keep console padding outside the terminal host so Vim's last row and rightmost columns remain visible.  
Keep output saving in the service so a browser disconnect does not lose a completed result.  
Replace the latest output instead of appending run history, as requested.  

## RUN

Install uv and Node.js 20.19 or later.  
IMD uses a POSIX pseudo-terminal and supports macOS and Linux.  

Build the frontend once.  

```sh
uv sync
cd frontend
npm ci
npm run build
cd ..
```

<!-- 4c4b9dad36a8 -->
```txt
Resolved 37 packages in 4ms
Checked 36 packages in 13ms

added 75 packages, and audited 76 packages in 1s

14 packages are looking for funding
  run `npm fund` for details

found 0 vulnerabilities
npm warn allow-scripts 2 packages have install scripts not yet covered by allowS
cripts:
npm warn allow-scripts   esbuild@0.28.2 (postinstall: node install.js)
npm warn allow-scripts   fsevents@2.3.3 (install: (install scripts present))
npm warn allow-scripts
npm warn allow-scripts Run `npm approve-scripts --allow-scripts-pending` to revi
ew, or `npm approve-scripts <pkg>` to allow.

> imd-frontend@0.1.0 build
> vite build

vite v7.3.7 building client environment for production...
✓ 198 modules transformed.
dist/index.html                     0.62 kB │ gzip:  0.35 kB
dist/assets/index-BMFLZ8d_.css     15.12 kB │ gzip:  4.09 kB
dist/assets/index-CqsQ6-NK.js      63.41 kB │ gzip: 24.73 kB
dist/assets/markdown-Btou6k2a.js  134.21 kB │ gzip: 57.39 kB
dist/assets/terminal-DP_gxef0.js  330.51 kB │ gzip: 83.39 kB
✓ built in 733ms
```

Install the command from this repository after building the frontend.  
The installation package includes the built frontend.  

```sh
uv tool install --reinstall .
```

<!-- 3d450f0088d1 -->
```txt
Resolved 26 packages in 886ms
      Built imd @ file:///Users/qubaitian/refac/imd
Prepared 26 packages in 453ms
Uninstalled 26 packages in 130ms
Installed 26 packages in 21ms
 ~ annotated-doc==0.0.5
 ~ annotated-types==0.8.0
 ~ anyio==4.15.1
 ~ click==8.5.0
 ~ fastapi==0.142.4
 ~ h11==0.16.0
 ~ httptools==0.8.0
 ~ idna==3.20
 ~ imd==0.1.0 (from file:///Users/qubaitian/refac/imd)
 ~ markdown-it-py==4.2.0
 ~ mdurl==0.1.2
 ~ opentelemetry-api==1.45.1
 ~ pydantic==2.13.5
 ~ pydantic-core==2.46.5
 ~ pyte==0.8.2
 ~ python-dotenv==1.2.4
 ~ pyyaml==6.0.3
 ~ starlette==1.7.0
 ~ typing-extensions==4.16.0
 ~ typing-inspection==0.4.4
 ~ uvicorn==0.54.0
 ~ uvloop==0.23.0
 ~ watchfiles==1.3.0
 ~ wcwidth==0.9.2
 ~ websockets==17.2
 ~ xonsh==0.24.2
Installed 1 executable: imd
```

Start or restart the IMD service.  

```sh
imd
```

<!-- 6b096c485ef3 -->
```txt
```

Open <http://localhost:8000/Users/qubaitian/refac/imd> in the browser.  
IMD opens `/Users/qubaitian/refac/imd/imd.md` and creates an empty file if it is missing.  
Use `http://localhost:8000/path/to/notes` for another existing workspace.  
Encode spaces and special characters in the directory URL.  
Open <http://localhost:8000> to use the service's starting directory.  
Run `imd` from a terminal or an executable block to restart the service.  
The browser reconnects after a brief disconnection.  
Restarting ends active runs and clears session variables and environment changes.  
Saved documents remain on disk.  
The command returns after the service is ready when run from an external terminal.  
The service remains running after that terminal closes.  
Read the service log at `$XDG_STATE_HOME/imd/service.log`, or `~/.local/state/imd/service.log` when that variable is absent.  
The previous `open`, `close`, `--root`, and `--port` arguments are removed.  

Open files from the sidebar.  
Use Edit or Split to change a document.  
Changes save automatically after a short pause.  
Use the Save button or `Cmd+S` on macOS and `Ctrl+S` on Linux to save immediately.  
Unsaved changes stay available when switching documents in the current browser tab.  
A browser refresh can clear changes that have not reached the service.  
The browser asks before leaving when there are unsaved changes.  
Saving rejects an edit if the file changed on disk since it was opened.  

### Copy a document reference

Open Edit or Split and select text in the editor.  
Press `Cmd+L` to copy a reference such as `@/Users/qubaitian/refac/imd/imd.md:1-3`.  
The reference contains the absolute workspace path and the document's relative path.  
A single selected line uses the form `:2-2`.  
Line numbers refer to Markdown source lines, not wrapped screen lines.  
Unsaved edits can make these line numbers differ from the file on disk.  
Copying does not save the document.  
Preview selections and console input are outside this feature.  

Chrome normally uses `Cmd+L` for its address bar.  
IMD cancels that default action when the editor receives `Cmd+L` with a selection.  
The tested Chrome on macOS needs no browser or system configuration.  
Confirm that IMD shows the copied reference and that pasting produces that reference.  
If the address bar still receives focus, that browser environment reserves the shortcut before IMD receives it.  
Changing Chrome's Open Location menu shortcut through macOS App Shortcuts is a possible workaround that needs a separate check in that environment.  
That change affects the address bar shortcut across Chrome, including other sites.  
See [Apple's App Shortcuts instructions](https://support.apple.com/guide/mac-help/mchlp2271/mac).  
Allow clipboard access if Chrome reports that copying failed.  

Only click Run for code you trust.  
Code can read and change files outside the workspace through the local process.  
The workspace boundary limits document access through the file API.  
The workspace boundary is not a sandbox for code execution.  

## DEVELOP

Start the Python service on its default port.  
Start the frontend development server in another terminal.  

```sh
cd frontend
npm run dev
```

Add the absolute workspace directory to the URL printed by Vite.  
Open that directory URL through the IMD service once to create `imd.md` if it is missing.  
Vite forwards the API and session connection to the Python service on port 8000.  

Run the checks from the repository directory.  

```sh
uv run pytest
uv run ruff check .
cd frontend
npm test
npm run check
npm run build
```
