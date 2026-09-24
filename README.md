# IMD — Interactive Markdown

## glossary

**IMD**:
A Markdown editor with command execution on the browser.  
_Avoid_: IDE, terminal

**Editor**:
The view that shows the whole Markdown file as plain text.  
_Avoid_: source view

**Preview**:
The view that shows the rendered Markdown with editable code blocks.  
_Avoid_: render, viewer

**Service**:
A background IMD process that serves one Markdown file to the browser.  
_Avoid_: server, daemon, session

**Service number**:
The position of a service in `imd list`, sorted by start time.  
_Avoid_: id, pid

**Service log**:
The file that holds the output of one service.  

**Code block**:
A fenced block of command or agent input in the Markdown file or a Markdown output block.  
_Avoid_: cell, snippet

**Agent**:
A command-line AI program that reads a prompt on stdin.  
_Avoid_: bot, model

**Agent config**:
The file `~/.config/imd/agents.json` that maps each agent name to a start command and a continue command.  

**Agent block**:
A code block whose first info word is an agent name.  
_Avoid_: prompt block

**Output block**:
The text between the `imd:output:begin` and `imd:output:end` markers right after a code block.  
_Avoid_: result, cell output

## Use

Run `npm install` in this directory.  
Run `npm test` to build and run all tests.  
Run `npm run build` to build the browser editor.  
Run `npm link` to make the `imd` command available on your path.  
Run `imd open` to start a service for a new temporary file for the current directory.  
Run `imd open filename.md` to start a service for a file relative to the current directory.  
Run `imd list` to show all services with their service numbers.  
Run `imd close` to stop all services.  
Run `imd close 2` to stop service number 2.  
Click EDITOR or PREVIEW at the top to switch the view.  
Type a command into a code block in the preview, then press Shift+Enter to run it.  
Press Shift+Enter in the editor with the cursor in a code block to run it and switch to the preview.  
Click run under a code block in the preview to run it.  
Click + code block at the end of the preview to add an empty code block.  
Click stop to stop the run.  
Click del on a code block to delete it and its output block.  
Click del on an output block to delete only the output block.  
Run a code block inside a Markdown output block the same way as any other code block.  
Code blocks inside `txt` output blocks are plain text.  
Type into the terminal under a running code block to answer its prompts.  
Write ```` ```sh md ```` to put the output in the file as Markdown.  
Other code blocks get their output in a `txt` fence:

    ```sh
    ls
    ```

    <!-- imd:output:begin 3f9a1c -->
    ```txt
    README.md
    ```
    <!-- imd:output:end 3f9a1c -->

Write a prompt in an agent block, such as ```` ```codex ````, and run it to send the prompt to the agent.  
The first run of an agent in a service uses its start command.  
Later runs of that agent use its continue command.  
Agent output goes into the file as Markdown.  
Put your agents in the agent config:

    {
      "codex": {
        "start": "codex exec -m gpt-6-sol -c model_reasoning_effort=high 2>>/tmp/imd/codex.log",
        "continue": "codex exec resume --last - 2>>/tmp/imd/codex.log"
      },
      "opencode": {
        "start": "opencode run -m 'opencode-go/glm-5.3#high'",
        "continue": "opencode run -c"
      },
      "cursor-agent": {
        "start": "cursor-agent -f -p --model claude-opus-5-5-medium",
        "continue": "cursor-agent -f -p --continue"
      },
      "pi": {
        "start": "pi -p --model opencode-go/grok-4.7:high",
        "continue": "pi -p -c"
      }
    }

## ADR

Use Svelte for a small browser bundle and a simple editor page.  
Run `imd open` to create and edit a temporary file under `/tmp` using the working directory path.  
Running it in `/Users/qubaitian/code/imd`:
    Creates a file such as `/tmp/Users/qubaitian/code/imd/2026-09-23_14-05-30-123.md`.  
Running `imd open note.md` in `/Users/qubaitian/code/imd`:
    Writes log to `/tmp/Users/qubaitian/code/imd/note.md.log`.  
Show one view at a time, and open in the preview, because running code blocks is the main use.  
Keep the hidden view on the page, so a running terminal survives a view switch.  
Use one shell per service, so `cd`, `export`, and `source` in one code block change every later run in the file.  
The shell starts with the directory and environment of `imd open`.  
The shell is always zsh without your rc files, because IMD needs its own zsh hooks to see where each command ends.  
Use `zsh -n` to split a code block into commands, and run them one by one.  
Lines that end with `\`, `|`, `&&`, or `||`, and open heredocs, join the next line, because `zsh -n` accepts them too early.  
Stop a run at the first command that fails, so later commands do not run in a broken state.  
Stop sends Ctrl+C, and kills the foreground process group after 2 seconds.  
Let the browser write the output block into the Markdown, and let the service only run commands.  
This keeps the textarea as the only writer of the file.  
Link an output block to its code block by position, right after the fence, and not by a stored ID.  
The ID only pairs the begin and end markers.  
Allow code blocks in Markdown output blocks at any depth, because generated Markdown may contain commands to run next.  
Treat `txt` output blocks as plain text, because command output may contain code fences.  
Replace a code block's whole output block on each run, including any nested code blocks.  
Use the `ws` package with `upgradeWebSocket` from `@hono/node-server`, because `@hono/node-ws` does not support `@hono/node-server` v2.  
Send the token as the first WebSocket message, because a browser cannot set headers on a WebSocket.  
Run `chmod +x` on the `node-pty` spawn helper after install, because its npm package ships the helper without the execute bit.  
The service remembers which agents have started, and the file does not.  
An agent counts as started only after a run that exits with 0, so a failed first run starts again.  
Run an agent as `{ command } < prompt-file` in the shared shell.  
The braces send the prompt to the whole command, and the prompt gets no shell expansion.  
Write agent output as Markdown without the `md` word, because agents answer in Markdown.  
Send agent logs on stderr to a log file with `2>>` in the command, so they stay out of the Markdown.  
IMD has no built-in agents, because model names in the commands change often.  
IMD reads the agent config on each run, so a change applies without a restart.  
A broken agent config fails every run, because IMD cannot tell an agent block from shell code.  
