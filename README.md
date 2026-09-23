# IMD — Interactive Markdown

## glossary

**IMD**:
A Markdown editor with command execution on the browser.  
_Avoid_: IDE, terminal

## Use

Run `npm install` in this directory.  
Run `npm test` to build and run all tests.  
Run `npm run build` to build the browser editor.  
Run `npm link` to make the `imd` command available on your path.  
Run `imd open` to edit a new temporary file for the current directory.  
Run `imd open filename.md` to edit a file relative to the current directory.  

## ADR

Use Svelte for a small browser bundle and a simple editor page.  
Run `imd open` to create and edit a temporary file under `/tmp` using the working directory path.  
Running it in `/Users/qubaitian/code/imd` creates a file such as `/tmp/Users/qubaitian/code/imd/2026-09-23_14-05-30-123.md`.  
