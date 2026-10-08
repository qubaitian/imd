# A notebook with a pulse.

Markdown for your thoughts.
**xonsh for everything you want to try.**

This document has its own session.
Run a block, then run the next one.
Your working directory, environment, and Python variables stay with this document.

## Start with a little Python

The `python` label makes this block executable.
IMD runs it through xonsh, just like every other executable block.

```python
name = "Markdown"
print(f"Hello, {name}.")
```

<!-- 1f8adaa5bc23 -->
```txt
Hello, Markdown.
```

## Bring your shell along

Shell commands and Python can share the same session.

```xonsh
$IMD_GREETING = 'Your session is alive'
pwd
print($IMD_GREETING + ', ' + name + '.')
```

## Change the directory

The next block will see the directory you choose here.

```sh
cd ..
pwd
```

```py
print('Current directory:', $PWD)
print('Still here:', name)
print('Environment:', $IMD_GREETING)
```

## Ask a question

Click Run, then type your answer in the output block.

```shell
answer = input('What would you like to build? ')
print('Next up:', answer)
```

> Each document starts in its own directory.
> Open another document to get a separate session.
> Use **Reset session** to start over.
