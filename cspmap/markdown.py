"""Small shared primitives for readable Markdown reports."""

from dataclasses import dataclass, field
from html import escape


def markdown_text(value: str) -> str:
    """Escape arbitrary identifiers used in Markdown table cells."""
    return escape(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def format_number(value, digits=2) -> str:
    """Display unavailable numeric measurements explicitly."""
    return f"{value:.{digits}f}" if value is not None else "N/A"


@dataclass
class MarkdownDocument:
    """Collect report lines and tables without owning business calculations."""

    lines: list[str] = field(default_factory=list)

    def table(self, headers, rows) -> None:
        self.lines.append("| " + " | ".join(headers) + " |")
        self.lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        self.lines.extend(
            "| " + " | ".join(str(value) for value in row) + " |" for row in rows
        )
        self.lines.append("")

    def write(self, path, trailing_newline=True) -> None:
        text = "\n".join(self.lines) + ("\n" if trailing_newline else "")
        path.write_text(text, encoding="utf-8")
