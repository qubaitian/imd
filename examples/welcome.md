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

<!-- b9f3a42efac6 -->
```txt
/Users/qubaitian/refac/imd/examples
Your session is alive, Markdown.
```

## Change the directory

The next block will see the directory you choose here.

```sh
cd ..
pwd
```

<!-- b231edf23d9e -->
```txt
/Users/qubaitian/refac/imd
```

```py
print('Current directory:', $PWD)
print('Still here:', name)
print('Environment:', $IMD_GREETING)
```

<!-- b2b3f1e59d59 -->
```txt
Current directory: /Users/qubaitian/refac/imd
Still here: Markdown
Environment: Your session is alive
```

## Ask a question

Click Run, then type your answer in the output block.

```shell
answer = input('What would you like to build? ')
print('Next up:', answer)
```

<!-- e8d35e17a22c -->
```txt
What would you like to build? eeee
Next up: eeee
```

> Each document starts in its own directory.
> Open another document to get a separate session.
> Use **Reset session** to start over.
