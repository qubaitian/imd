"""Plain output from a terminal's normal screen and scrollback."""

from copy import deepcopy

import pyte


class NormalScreen(pyte.HistoryScreen):
    def __init__(self, columns, rows):
        self._normal = None
        super().__init__(columns, rows, history=5000)

    def select_graphic_rendition(self, *attributes, **kwargs):
        if not kwargs.get("private"):
            super().select_graphic_rendition(*attributes)

    def set_mode(self, *modes, **kwargs):
        alternate = {47, 1047, 1049} if kwargs.get("private") else set()
        if alternate.intersection(modes) and self._normal is None:
            self._normal = deepcopy(
                {key: value for key, value in vars(self).items() if key != "_normal"}
            )
            self.reset()
        super().set_mode(*(mode for mode in modes if mode not in alternate), **kwargs)

    def reset_mode(self, *modes, **kwargs):
        alternate = {47, 1047, 1049} if kwargs.get("private") else set()
        if alternate.intersection(modes) and self._normal is not None:
            columns, rows = self.columns, self.lines
            vars(self).update(self._normal)
            self._normal = None
            self.resize(lines=rows, columns=columns)
        super().reset_mode(*(mode for mode in modes if mode not in alternate), **kwargs)


class TerminalCapture:
    def __init__(self, columns: int, rows: int):
        self.screen = NormalScreen(columns, rows)
        self.stream = pyte.Stream(self.screen)

    def write(self, text: str):
        self.stream.feed(text)

    def resize(self, columns: int, rows: int):
        self.screen.resize(lines=rows, columns=columns)

    def text(self) -> str:
        screen = self.screen
        if screen._normal is not None:
            screen = deepcopy(screen)
            vars(screen).update(screen._normal)
        history = [
            "".join(line[column].data for column in range(screen.columns)).rstrip()
            for line in screen.history.top
        ]
        lines = history + [line.rstrip() for line in screen.display]
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines) + ("\n" if lines else "")
