# IMD — Interactive Markdown

## glossary

**IMD**:
A Markdown editor with command execution on the browser.  
_Avoid_: IDE, terminal

**Service**:
A background IMD process that serves one Markdown file to the browser.  
_Avoid_: server, daemon, session

**Service number**:
The position of a service in `imd list`, sorted by start time.  
_Avoid_: id, pid

**Service log**:
The file that holds the output of one service.  

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

## ADR

Use Svelte for a small browser bundle and a simple editor page.  
Run `imd open` to create and edit a temporary file under `/tmp` using the working directory path.  
Running it in `/Users/qubaitian/code/imd` creates a file such as `/tmp/Users/qubaitian/code/imd/2026-09-23_14-05-30-123.md`.  
Running `imd open note.md` in `/Users/qubaitian/code/imd` writes `/tmp/Users/qubaitian/code/imd/note.md.log`.  
