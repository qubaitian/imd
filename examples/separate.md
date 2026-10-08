# A separate session

This document has a different session from `welcome.md`.
It starts in this file's directory.

```xonsh
pwd
print('name from welcome exists:', 'name' in globals())
print('greeting from welcome exists:', 'IMD_GREETING' in __xonsh__.env)
```

Set a variable here, then return to this document later.

```python
local_value = 123
print(local_value)
```
