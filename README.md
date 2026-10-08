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
**Editor**: The text area containing a document's Markdown source.  
**Preview view**: A document view containing rendered Markdown.  
**Edit view**: A document view containing the editor.  
**Split view**: A document view containing the editor beside rendered Markdown.  
**Selection**: A nonempty range of text in the editor.  
**Document reference**: Plain text in the form `@/absolute/document/path.md:start-end` with inclusive source line numbers starting at 1.  
**Code block**: A fenced section of a document with an optional language label.  
**Code block editor**: A text area for the body of a code block in Preview or Split view.  
**Agent block**: A code block with the label `agent`.  
**Output marker**: A unique hexadecimal identifier in a Markdown comment after a code block.  
**Output block**: A `txt` code block linked by an output marker to the preceding code block, containing the latest run's plain terminal output.  
**Executable block**: Any code block other than an output block.  
**Session**: A persistent xonsh process for one document, with its own working directory, environment, and Python variables.  
**Session connection**: A WebSocket connection between one browser page and a document session.  
**Run**: One execution of an executable block inside its document's session.  
**Agent command**: A program and its fixed arguments configured in a document's session for an external coding agent.  
**Agent stdout**: The standard output stream of an agent command.  
**Agent stderr**: The standard error stream of an agent command.  
**Agent log**: A local file containing agent stderr from the latest run.  
**First command**: The agent command for prompts before the first success in a session.  
**Continue command**: The agent command for later prompts in the same session.  
**Prompt**: The complete text of an agent block submitted to an agent command after configuration.  
**Console**: The temporary xterm view inside an output block during a run.  
**Terminal host**: The container without padding inside a console that defines the terminal screen's available space.  
**IMD**: A browser editor for workspace documents with executable blocks and output blocks.  

## DESIGN

The browser connects to the IMD service.  
`imd` starts the IMD service on port 8000 when it is stopped.  
`imd` restarts the IMD service when it is running.  
The restart process starts outside the document session before stopping the old service.  
The IMD service runs in the background after the command ends.  
A browser page opens one session connection for each document it opens.  
A failed or closed session connection stays disconnected.  
The user refreshes the browser page to connect again.  
A missing document shows a reason in the browser.  
The command does not open a new browser tab.  
Restarting the service ends all sessions and clears their state.  
A directory URL opens the default document and creates an empty file if it is missing.  
An existing default document keeps its content.  
Different directory URLs select different workspaces in the same service.  
A missing directory returns an error.  
Each document has one session shared by all browser tabs that open that document.  
Different documents have separate sessions.  
Every code block except an output block has a Run button, with or without a language label.  
Executable blocks use xonsh syntax unless the block is an agent block or agent configuration.  
Language labels stay unchanged in the document.  
A missing language label appears as `xonsh` in the preview.  
IMD does not check whether code can run before showing Run.  
The user decides whether to run each block.  
A standalone `txt` block is executable.  
Runs in one session execute in order.  
A session starts in the document's directory.  
The session remains available after a browser refresh.  
Resetting a session clears its state.  
Stopping the service ends all sessions.  

A `sh` block can configure agent commands with `imd set agent first PROGRAM [ARGUMENTS]` and `imd set agent continue PROGRAM [ARGUMENTS]`.  
Run the configuration block before running a prompt block.  
Both commands are required before submitting a prompt.  
After configuration, the Run button submits each agent block as one prompt argument.  
An agent block without configuration returns an error.  
Text inside an agent block is always a prompt, including agent configuration examples.  
The prompt keeps its complete text, including newlines and quotes.  
The first command is used until a prompt succeeds.  
Later prompts use the continue command.  
A failed or interrupted prompt keeps the current command choice.  
Setting the first command starts a new sequence of prompts.  
Configuration blocks contain only configuration lines, blank lines, and shell comments.  
The first line that is neither blank nor a shell comment identifies a configuration block.  
Invalid configuration leaves the previous commands unchanged.  
Agent commands use the session's current directory and environment.  
Agent output, input, interruption, and saving use the existing console and output block.  
`imd set agent stderr PATH` configures an agent log for both agent commands.  
The path is a literal path relative to the session's current directory at run time, or an absolute path.  
Each agent run creates or overwrites the agent log.  
The parent directory must already exist.  
Agent stdout remains in the console and output block.  
Run failures remain visible in the console.  
`imd set agent stderr` returns agent stderr to the console.  
Changing the agent log keeps the current first or continue command choice.  
Use any non-agent executable block for code after agent configuration.  
Agent configuration is shared by browser tabs for the same document.  
Resetting a session or restarting the service clears its agent configuration.  

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
Click a code block's body or focus it and press Enter to open its code block editor.  
Leaving the code block editor restores the rendered code.  
Code block changes use the document's automatic save.  
Output blocks and queued or running executable blocks are not editable in the preview.  
`Cmd+L` copies a document reference for the selection when the browser passes the shortcut to the editor.  
The document reference uses the editor's current source, including unsaved changes.  
An end position at the start of the next line excludes that line.  
An empty selection leaves the clipboard unchanged.  
Copying shows a confirmation or an error without changing the selection.  
Output updates preserve other changes already saved in the document.  
Conflicting edits remain in the editor with a visible error.  

## ADR

### Run for every ordinary code block

Offer Run for every code block except saved output instead of using a language whitelist.  
The user decides whether the code is suitable for execution.  
Keep xonsh as the shared interpreter instead of selecting interpreters from language labels.  
All ordinary code blocks share the document session's state.  
Keep language labels and source text unchanged.  
Identify output blocks by their output markers instead of excluding all `txt` blocks.  
A standalone `txt` block is ordinary code.  
Keep saved output without Run because it is the result of another block.  
Keep `agent` prompts and `sh` agent configuration under their existing rules.  

### Code block editing in the preview

Use a text area for each active code block editor instead of replacing the document editor with a rich text library.  
Only code block bodies need direct editing.  
Keep the code block editor mounted during preview updates so typing and terminal output do not reset its selection.  
Replace source lines instead of serializing rendered HTML so surrounding Markdown and output markers stay unchanged.  
Keep output blocks read-only because a run owns their content.  
Keep queued and running code blocks read-only so visible code stays consistent with the submitted run.  

### Frontend component tests

Use jsdom with Vitest for component tests instead of testing only Markdown strings.  
A rendered code block can have correct HTML while its editor cannot receive clicks.  
Use Svelte's browser condition for component tests because its server runtime does not run browser effects.  
Keep module tests in a separate Vitest project so their runtime stays unchanged.  
Check the full app in Preview and Split view through clicks and text input.  

### Agent commands in a document session

Recognize `imd set agent` inside the document worker instead of the service startup command.  
The worker owns the document's session state.  
Use agent blocks and their existing Run buttons instead of adding a separate prompt editor.  
Use the `agent` label instead of inspecting prompt text for configuration commands.  
A prompt can quote configuration commands without changing their state or needing special escaping.  
Keep `sh` and the other code labels available for xonsh code after configuration.  
Keep agent configuration in the session instead of a separate configuration file, as requested.  
Split command arguments with shlex instead of evaluating shell source.  
Quoted arguments can contain spaces without adding shell expansion or pipelines.  
Append the complete prompt as one literal argument instead of inserting it into command source.  
Prompt text can contain quotes and shell expressions.  
Use xonsh's existing subprocess runner instead of a second process manager.  
It preserves the session environment, foreground terminal input, and interruption behavior.  
Choose the continue command after a successful first prompt instead of after any attempt.  
A failed or interrupted first attempt may not have created an agent conversation.  

### Agent stderr in a local log

Use a separate `imd set agent stderr` setting instead of repeating a shell wrapper in both agent commands.  
Keep this setting available for any agent program instead of adding a Codex-specific command.  
Pass a structured redirection to xonsh instead of changing the worker's standard error stream.  
Only the agent command uses the agent log.  
The worker keeps reporting run failures in the console.  
Keep xonsh's existing process runner for foreground input and interruption.  
Overwrite the agent log instead of appending because it contains the latest run, like the output block.  
Treat log paths as literal arguments instead of shell source.  

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
Keep existing browser pages open after a restart.  
The user refreshes the page to connect again.  
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
Run every non-agent executable block through xonsh instead of separate shell and Python interpreters.  
Separate interpreters would split the document's state.  

### Local service and process boundary

Use FastAPI for the file API and the session WebSocket.  
FastAPI keeps HTTP and WebSocket handling in one async service.  
A separate socket service would split session lifecycle management.  
Use a pseudo-terminal for session input and output.  
Use a separate control channel for run completion because command output can contain arbitrary text.  
Start the worker with the same package directory as the IMD service instead of relying on Python's script import path.  
A service started from the repository can otherwise mix new worker code with an older installed package.  
Keep each session in a separate process because xonsh has process-wide state.  
Bind the service to the loopback interface and require a same-origin browser connection.  
Accept a same-origin connection before closing it for an unavailable document.  
Use WebSocket close code 1008 with a reason instead of rejecting that document's handshake.  
A rejected handshake appears as code 1006 in browsers without the service reason.  
Keep origin checks before the handshake.  
Executable blocks have the same permissions as the local service.  

### Session connection after disconnection

Use a browser page refresh to connect again instead of automatic retries, as requested.  
Repeated rejected connections fill the service log without restoring the session connection.  
Keep the page disconnected until the user refreshes it.  

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
Resolved 37 packages in 12ms
Checked 36 packages in 10ms

added 75 packages, and audited 76 packages in 2s

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
✓ 200 modules transformed.
dist/index.html                     0.62 kB │ gzip:  0.34 kB
dist/assets/index-DMsVpGNA.css     15.57 kB │ gzip:  4.16 kB
dist/assets/index-Dr4Gmku6.js      66.55 kB │ gzip: 25.86 kB
dist/assets/markdown-Btou6k2a.js  134.21 kB │ gzip: 57.39 kB
dist/assets/terminal-DP_gxef0.js  330.51 kB │ gzip: 83.39 kB
✓ built in 746ms
```

Install the command from this repository after building the frontend.  
The installation package includes the built frontend.  

```sh
uv tool install --reinstall .
```

<!-- 3d450f0088d1 -->
```txt
Resolved 26 packages in 605ms
   Building imd @ file:///Users/qubaitian/refac/imd
      Built imd @ file:///Users/qubaitian/refac/imd
Prepared 26 packages in 429ms
Uninstalled 26 packages in 125ms
Installed 26 packages in 18ms
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
Run `imd` from a terminal or a `xonsh` block to restart the service.  
Refresh the browser page after a disconnection to connect again.  
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

### Configure agent commands

Add this configuration to a `sh` block in your document.  
Click its Run button once.  
The configuration commands are available inside IMD document runs.  

```sh
# Agent commands for this document session.
imd set agent first cursor-agent -f -p --model grok-4.7-high
imd set agent continue cursor-agent -f -p --continue
```

Add each prompt to an agent block and click Run.  

```agent
Please review the code.
```

The first successful prompt uses the first command.  
Later prompts use the continue command.  
The agent program must be installed and available in the session's PATH.  
The configured agent program owns its conversation history.  
IMD chooses the command and does not manage the agent program's conversation identifiers.  

For Codex CLI, send agent stderr to an agent log to keep process messages out of the output block.  
Use the ordinary text mode instead of `--json`, which writes events to stdout.  

```sh
imd set agent stderr codex.log
imd set agent first codex exec -m gpt-6.1-sol -c model_reasoning_effort=medium
imd set agent continue codex exec resume --last
```

Each run overwrites `codex.log` in the session's current directory.  
Read this file when an agent run fails.  
Use `imd set agent stderr` to show agent stderr in the console again.  

Use shell comments for explanations inside a configuration block.  
Use `sh` or `xonsh` blocks for ordinary commands after configuring an agent.  
Run the configuration block again after resetting the session or restarting the service.  

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
