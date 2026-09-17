class Output:
    """Apply text cursor controls to the saved output."""

    def __init__(self):
        self.clear()

    def clear(self):
        self.lines = [[]]
        self.row = self.column = 0
        self.escape = ""

    @property
    def text(self):
        return "\n".join("".join(line) for line in self.lines)

    def feed(self, text):
        for char in text:
            if self.escape:
                self.escape += char
                if self.escape.startswith("\x1b["):
                    if len(self.escape) > 2 and "@" <= char <= "~":
                        self._control(self.escape[2:-1], char)
                        self.escape = ""
                elif self.escape.startswith(("\x1b]", "\x1bP")):
                    if char == "\x07" or self.escape.endswith("\x1b\\"):
                        self.escape = ""
                elif len(self.escape) == 2:
                    self.escape = ""
                continue
            if char == "\x1b":
                self.escape = char
            elif char == "\r":
                self.column = 0
            elif char == "\n":
                self.row += 1
                self.column = 0
                self._line()
            elif char == "\b":
                self.column = max(0, self.column - 1)
            elif char == "\t":
                self.column = (self.column // 8 + 1) * 8
            elif char >= " " and char != "\x7f":
                line = self._line()
                if len(line) <= self.column:
                    line.extend(" " for _ in range(self.column + 1 - len(line)))
                line[self.column] = char
                self.column += 1

    def _line(self):
        while len(self.lines) <= self.row:
            self.lines.append([])
        return self.lines[self.row]

    def _control(self, parameters, command):
        if any(char not in "0123456789;" for char in parameters):
            return
        values = [min(int(part or 0), 10000) for part in parameters.split(";")]
        count = values[0] or 1
        if command == "A":
            self.row = max(0, self.row - count)
        elif command == "B":
            self.row = min(10000, self.row + count)
        elif command == "C":
            self.column = min(10000, self.column + count)
        elif command == "D":
            self.column = max(0, self.column - count)
        elif command == "G":
            self.column = count - 1
        elif command in {"H", "f"}:
            self.row = count - 1
            self.column = (values[1] or 1) - 1 if len(values) > 1 else 0
        elif command == "K":
            line = self._line()
            if values[0] == 0:
                del line[self.column :]
            elif values[0] == 1:
                end = min(len(line), self.column + 1)
                line[:end] = [" "] * end
            elif values[0] == 2:
                line.clear()
        elif command == "J":
            if values[0] in {2, 3}:
                self.lines = [[] for _ in range(self.row + 1)]
            elif values[0] == 0:
                del self._line()[self.column :]
                del self.lines[self.row + 1 :]
