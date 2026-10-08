# IMD — Interactive Markdown

IMD is a local Markdown editor with code execution in the browser.  

## TERM

**Workspace**: The local directory containing the documents available to IMD.  
**Document**: A Markdown file inside the workspace.  
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

The browser connects to a local Python service.  
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
Output updates preserve other changes already saved in the document.  
Conflicting edits remain in the editor with a visible error.  

## ADR

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

Start the service with the example workspace.  

```sh
uv run imd --root examples
```

Open <http://127.0.0.1:8000> in the browser.  
Open `welcome.md` and run its blocks in order.  
Open `separate.md` to try an independent session.  

Use `uv run imd --root /path/to/notes` for your own workspace.  
Use `--port 8080` to choose another port.  
Open files from the sidebar.  
Use Edit or Split to change a document.  
Changes save automatically after a short pause.  
Use the Save button or `Cmd+S` on macOS and `Ctrl+S` on Linux to save immediately.  
Unsaved changes stay available when switching documents in the current browser tab.  
A browser refresh can clear changes that have not reached the service.  
The browser asks before leaving when there are unsaved changes.  
Saving rejects an edit if the file changed on disk since it was opened.  

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

Use the URL printed by Vite.  
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
