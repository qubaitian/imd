# Make Markdown run.

Write ideas in text. Check ideas with code.  
Each run stores the result in this Markdown file.  

> Click any text or code block to start an edit.  
> Press **Shift + Enter** to run the current code block. Press **Enter** to add a line.  

## Talk to this computer

A block with no language tag or with the `shell` tag runs in the shell of this document.  
Environment variables, the working directory, aliases, and functions stay between blocks.  

```shell
export IMD_MESSAGE=Hello, Markdown!
cd /tmp
```

<!-- imd:output:begin example-shell-state -->

<!-- imd:output:end example-shell-state -->

```shell
echo "$IMD_MESSAGE"
pwd
```

<!-- imd:output:begin example-shell-read -->

Hello, Markdown!
/tmp

<!-- imd:output:end example-shell-read -->

## Explore data with Python

A `python` block runs as a script with the `python3` of the same shell.  
The script reads the exported variables and the working directory of the shell.  
Each block starts a new Python process, so print every result that you want to keep.  

```python
values = [18, 24, 32, 26]

print(f"Total: {sum(values)}")
print(f"Average: {sum(values) / len(values):.1f}")
```

<!-- imd:output:begin example-python -->

Total: 100
Average: 25.0

<!-- imd:output:end example-python -->

---

- [x] Ordinary Markdown file
- [x] One shell for the whole document
- [x] Code and output stay together
