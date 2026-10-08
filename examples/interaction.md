# Interactive output

Each output block is a terminal while its code is running.  
Click inside the terminal to type.  
The completed output saves in this Markdown file automatically.  

## Answer a question

```python
answer = input('Continue? (y/n) ')
print('Your answer:', answer)
```

<!-- 9b1bd2110087 -->
```txt
Continue? (y/n) y
Your answer: y
```

## Use an arrow key

This block waits for one arrow key.  

```python
import sys
import termios
import tty

print('Press an arrow key.', flush=True)
settings = termios.tcgetattr(sys.stdin)
try:
    tty.setraw(sys.stdin.fileno())
    key = sys.stdin.read(3)
finally:
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
print('Key:', repr(key))
```

<!-- b3bd5d367b90 -->
```txt
Press an arrow key.
Key: '\x1b[B'
```

## Open Vim

This block opens a temporary file without loading a Vim configuration.  
Type `i` to insert text.  
Press Escape and type `:wq` followed by Enter to save and exit.  
Vim saves the edited file separately from this document's output.  

```xonsh
vim -Nu NONE -i NONE -n /tmp/imd-vim.txt
print('Vim finished.')
```

<!-- cac467914f0b -->
```txt
Vim finished.
```
