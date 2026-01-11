"""Markdown building utilities for documentation generation."""

from __future__ import annotations

from typing import Any, Dict, List


class MarkdownBuilder:
    """Efficient Markdown document builder using list accumulation."""

    def __init__(self):
        """Initialize a new Markdown builder."""
        self._lines: List[str] = []

    def add_line(self, line: str = "") -> "MarkdownBuilder":
        """
        Add a single line to the document.
        
        Parameters
        ----------
        line : str, optional
            Line to add, by default "".
            
        Returns
        -------
        MarkdownBuilder
            Self for method chaining.
        """
        self._lines.append(line)
        return self

    def add_lines(self, *lines: str) -> "MarkdownBuilder":
        """
        Add multiple lines to the document.
        
        Parameters
        ----------
        *lines : str
            Lines to add.
            
        Returns
        -------
        MarkdownBuilder
            Self for method chaining.
        """
        self._lines.extend(lines)
        return self

    def add_heading(self, text: str, level: int = 1) -> "MarkdownBuilder":
        """
        Add a heading.
        
        Parameters
        ----------
        text : str
            Heading text.
        level : int, optional
            Heading level (1-6), by default 1.
            
        Returns
        -------
        MarkdownBuilder
            Self for method chaining.
        """
        prefix = "#" * max(1, min(level, 6))
        self._lines.append(f"{prefix} {text}")
        return self

    def add_paragraph(self, text: str) -> "MarkdownBuilder":
        """
        Add a paragraph with blank line after.
        
        Parameters
        ----------
        text : str
            Paragraph text.
            
        Returns
        -------
        MarkdownBuilder
            Self for method chaining.
        """
        self._lines.append(text)
        self._lines.append("")
        return self

    def add_list_item(self, text: str, indent: int = 0) -> "MarkdownBuilder":
        """
        Add a list item.
        
        Parameters
        ----------
        text : str
            List item text.
        indent : int, optional
            Indentation level (number of spaces), by default 0.
            
        Returns
        -------
        MarkdownBuilder
            Self for method chaining.
        """
        prefix = " " * indent + "- "
        self._lines.append(f"{prefix}{text}")
        return self

    def add_ordered_item(self, text: str, number: int = 1, indent: int = 0) -> "MarkdownBuilder":
        """
        Add an ordered list item.
        
        Parameters
        ----------
        text : str
            List item text.
        number : int, optional
            Item number, by default 1.
        indent : int, optional
            Indentation level (number of spaces), by default 0.
            
        Returns
        -------
        MarkdownBuilder
            Self for method chaining.
        """
        prefix = " " * indent + f"{number}. "
        self._lines.append(f"{prefix}{text}")
        return self

    def add_code_block(self, code: str, language: str = "") -> "MarkdownBuilder":
        """
        Add a code block.
        
        Parameters
        ----------
        code : str
            Code content.
        language : str, optional
            Language hint, by default "".
            
        Returns
        -------
        MarkdownBuilder
            Self for method chaining.
        """
        self._lines.append(f"```{language}")
        self._lines.append(code.rstrip())
        self._lines.append("```")
        return self

    def add_quote(self, text: str) -> "MarkdownBuilder":
        """
        Add a blockquote.
        
        Parameters
        ----------
        text : str
            Quote text.
            
        Returns
        -------
        MarkdownBuilder
            Self for method chaining.
        """
        self._lines.append(f"> {text}")
        return self

    def add_horizontal_rule(self) -> "MarkdownBuilder":
        """
        Add a horizontal rule.
        
        Returns
        -------
        MarkdownBuilder
            Self for method chaining.
        """
        self._lines.append("---")
        return self

    def add_table_header(self, headers: List[str], alignments: List[str] | None = None) -> "MarkdownBuilder":
        """
        Add a table header row.
        
        Parameters
        ----------
        headers : List[str]
            Column headers.
        alignments : List[str] | None, optional
            Alignment for each column ('left', 'center', 'right'), by default None.
            
        Returns
        -------
        MarkdownBuilder
            Self for method chaining.
        """
        self._lines.append("| " + " | ".join(headers) + " |")
        
        if alignments:
            align_row = []
            for align in alignments:
                if align == "center":
                    align_row.append(":---:")
                elif align == "right":
                    align_row.append("---:")
                else:
                    align_row.append("---")
        else:
            align_row = ["---"] * len(headers)
        
        self._lines.append("|" + "|".join(align_row) + "|")
        return self

    def add_table_row(self, cells: List[str]) -> "MarkdownBuilder":
        """
        Add a table row.
        
        Parameters
        ----------
        cells : List[str]
            Cell contents.
            
        Returns
        -------
        MarkdownBuilder
            Self for method chaining.
        """
        self._lines.append("| " + " | ".join(str(c) for c in cells) + " |")
        return self

    def add_link(self, text: str, url: str, title: str = "") -> "MarkdownBuilder":
        """
        Add a link as a standalone line.
        
        Parameters
        ----------
        text : str
            Link text.
        url : str
            Link URL.
        title : str, optional
            Link title attribute, by default "".
            
        Returns
        -------
        MarkdownBuilder
            Self for method chaining.
        """
        if title:
            self._lines.append(f'[{text}]({url} "{title}")')
        else:
            self._lines.append(f"[{text}]({url})")
        return self

    def add_image(self, alt: str, url: str, title: str = "") -> "MarkdownBuilder":
        """
        Add an image.
        
        Parameters
        ----------
        alt : str
            Alt text.
        url : str
            Image URL.
        title : str, optional
            Image title, by default "".
            
        Returns
        -------
        MarkdownBuilder
            Self for method chaining.
        """
        if title:
            self._lines.append(f'![{alt}]({url} "{title}")')
        else:
            self._lines.append(f"![{alt}]({url})")
        return self

    def add_blank_line(self) -> "MarkdownBuilder":
        """
        Add a blank line.
        
        Returns
        -------
        MarkdownBuilder
            Self for method chaining.
        """
        self._lines.append("")
        return self

    def build(self) -> str:
        """
        Build the final Markdown document.
        
        Returns
        -------
        str
            Complete Markdown document as string.
        """
        return "\n".join(self._lines).strip() + "\n"

    def clear(self) -> "MarkdownBuilder":
        """
        Clear all lines from the builder.
        
        Returns
        -------
        MarkdownBuilder
            Self for method chaining.
        """
        self._lines.clear()
        return self

    @staticmethod
    def bold(text: str) -> str:
        """Format text as bold."""
        return f"**{text}**"

    @staticmethod
    def italic(text: str) -> str:
        """Format text as italic."""
        return f"*{text}*"

    @staticmethod
    def code(text: str) -> str:
        """Format text as inline code."""
        return f"`{text}`"

    @staticmethod
    def link(text: str, url: str, title: str = "") -> str:
        """Create a markdown link."""
        if title:
            return f'[{text}]({url} "{title}")'
        return f"[{text}]({url})"
