from __future__ import annotations

import os
import sys
from typing import Optional


class ConsoleUI:
    _COLORS = {
        "info": "36",      # cyan
        "success": "32",   # green
        "warning": "33",   # yellow
        "error": "31",     # red
        "muted": "90",     # bright black / grey
    }
    _LABELS = {
        "info": "INFO",
        "success": "DONE",
        "warning": "WARN",
        "error": "ERR",
        "muted": "...",
    }

    def __init__(self) -> None:
        self._supports_ansi = sys.stdout.isatty() and os.getenv("TERM") != "dumb"
        self._status_line: Optional[str] = None
        self._status_level = "info"
        self._detail_line: Optional[str] = None
        self._detail_level = "muted"
        self._progress_line: Optional[str] = None
        self._rendered_lines = 0
        self._last_progress_length = 0

        if os.name == "nt" and self._supports_ansi:
            try:
                import colorama
            except ImportError:
                self._supports_ansi = False
            else:
                colorama.just_fix_windows_console()

    def _format_plain(self, message: str, level: str, *, indent: bool = False) -> str:
        if level == "muted":
            prefix = "  " if indent else ""
            return f"{prefix}{message}"
        label = self._LABELS.get(level, level.upper())
        prefix = f"[{label}] "
        if indent:
            prefix = "  " + prefix
        return prefix + message

    def _colorize(self, text: str, level: str) -> str:
        if not self._supports_ansi:
            return text
        code = self._COLORS.get(level)
        if not code:
            return text
        return f"\x1b[{code}m{text}\x1b[0m"

    def _clear_fallback_line(self) -> None:
        if not self._last_progress_length:
            return
        sys.stdout.write("\r" + " " * self._last_progress_length + "\r")
        sys.stdout.flush()
        self._last_progress_length = 0

    def _clear_render(self) -> None:
        if not self._supports_ansi or not self._rendered_lines:
            return
        sys.stdout.write("\r")
        for index in range(self._rendered_lines):
            sys.stdout.write("\x1b[2K")
            if index < self._rendered_lines - 1:
                sys.stdout.write("\x1b[1A")
        sys.stdout.write("\r")
        sys.stdout.flush()
        self._rendered_lines = 0

    def _render(self) -> None:
        if not self._supports_ansi:
            return
        lines = self._compose_box_lines()
        self._clear_render()
        if not lines:
            return
        for idx, line in enumerate(lines):
            if idx:
                sys.stdout.write("\n")
            sys.stdout.write(line)
        sys.stdout.flush()
        self._rendered_lines = len(lines)

    def _compose_box_lines(self) -> list[str]:
        sections: list[tuple[str, str, list[str]]] = []
        progress_lines: list[str] = []
        if self._progress_line:
            if self._status_line:
                progress_lines.extend(self._status_line.splitlines())
            progress_lines.extend(self._progress_line.splitlines())
            sections.append(("Progress", "info", progress_lines))
        elif self._status_line:
            sections.append(("Status", self._status_level, self._status_line.splitlines()))

        if self._detail_line:
            sections.append(("Detail", self._detail_level, self._detail_line.splitlines()))

        formatted: list[str] = []
        for idx, (title, level, content_lines) in enumerate(sections):
            content = content_lines or [""]
            label = self._LABELS.get(level, level.upper()) if level else ""
            header_text = f"{title.upper()}" + (f" :: {label}" if label else "")
            inner_width = max(len(header_text), max(len(line) for line in content))
            horizontal = "+" + "-" * (inner_width + 2) + "+"
            formatted.append(horizontal)

            header_line_text = header_text.center(inner_width)
            if level:
                header_line_text = self._colorize(header_line_text, level)
            formatted.append(f"| {header_line_text} |")
            formatted.append("+" + "-" * (inner_width + 2) + "+")

            for line in content:
                text = line.ljust(inner_width)
                if level:
                    text = self._colorize(text, level)
                formatted.append(f"| {text} |")
            formatted.append(horizontal)
            if idx != len(sections) - 1:
                formatted.append("")
        return formatted

    def _render_fallback(self) -> None:
        components: list[str] = []
        if self._progress_line:
            if self._status_line:
                components.append(self._format_plain(self._status_line, self._status_level))
            components.append(self._progress_line)
        elif self._status_line:
            components.append(self._format_plain(self._status_line, self._status_level))

        if self._detail_line:
            components.append(self._format_plain(self._detail_line, self._detail_level))

        if not components:
            self._clear_fallback_line()
            return
        combined = " | ".join(components)
        padding = max(0, self._last_progress_length - len(combined))
        sys.stdout.write("\r" + combined + " " * padding)
        sys.stdout.flush()
        self._last_progress_length = len(combined)

    def update_status(self, message: str, *, level: str = "info") -> None:
        if not self._supports_ansi:
            self._status_line = self._format_plain(message, level)
            self._status_level = level
            self._render_fallback()
            return
        self._status_line = message
        self._status_level = level
        self._render()

    def update_detail(self, message: Optional[str], *, level: str = "muted") -> None:
        if not self._supports_ansi:
            if message is None:
                self._detail_line = None
            else:
                self._detail_line = self._format_plain(message, level, indent=True)
                self._detail_level = level
            self._render_fallback()
            return
        self._detail_line = message
        self._detail_level = level
        self._render()

    def update_progress(self, message: Optional[str]) -> None:
        if not self._supports_ansi:
            if message is not None:
                padding = max(0, self._last_progress_length - len(message))
                sys.stdout.write("\r" + message + " " * padding)
                sys.stdout.flush()
                self._last_progress_length = len(message)
            else:
                self._clear_fallback_line()
            return
        self._progress_line = message
        self._render()

    def log_event(self, message: str, *, level: str = "info") -> None:
        if not self._supports_ansi:
            print(self._format_plain(message, level), flush=True)
            return
        self._clear_render()
        print(self._colorize(message, level), flush=True)
        self._render()

    def finalize(self) -> None:
        if not self._supports_ansi:
            self._clear_fallback_line()
            return
        self._clear_render()