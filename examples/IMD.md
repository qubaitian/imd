# Make Markdown run.

Write ideas in text. Check ideas with code.  
Each run stores the result in this Markdown file.  

> Click any text or code block to start an edit.  
> Press **Shift + Enter** to run the current code block. Press **Enter** to add a line.  

## Explore data with Python

Start with a small set of data.  
Later code blocks can use the variables that you define here.  

```python
values = [18, 24, 32, 26]
print(f"Total: {sum(values)}")
print(f"Average: {sum(values) / len(values):.1f}")
```

```out
Total: 100
Average: 25.0
```

## Talk to this computer

Shell code blocks use the same IPython session.  
`cd` changes the working directory. `env` sets an environment variable.  

```shell
env IMD_MESSAGE=Hello, Markdown!
!echo "$IMD_MESSAGE"
```

```out
env: IMD_MESSAGE=Hello, Markdown!
Hello, Markdown!
```

---

- [x] Ordinary Markdown file
- [x] Python and shell share a session
- [x] Code and output stay together
