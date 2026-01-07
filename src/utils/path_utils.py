"""Path handling utilities for documentation generation."""

from __future__ import annotations

import pathlib
import re
from typing import List


class PathUtils:
    """Centralized path manipulation utilities."""

    @staticmethod
    def normalize_path(path: str) -> str:
        """
        Normalize path to forward slashes.
        
        Parameters
        ----------
        path : str
            Path to normalize.
            
        Returns
        -------
        str
            Normalized path with forward slashes.
        """
        return (path or "").replace("\\", "/")

    @staticmethod
    def strip_drive_letter(path: str) -> str:
        """
        Remove Windows drive letter from path.
        
        Parameters
        ----------
        path : str
            Path that may contain a drive letter.
            
        Returns
        -------
        str
            Path without drive letter.
        """
        normalized = PathUtils.normalize_path(path)
        return re.sub(r"^[a-z]:/", "", normalized, flags=re.IGNORECASE)

    @staticmethod
    def split_segments(path: str) -> List[str]:
        """
        Split path into segments, removing drive letters.
        
        Parameters
        ----------
        path : str
            Path to split.
            
        Returns
        -------
        List[str]
            List of path segments.
        """
        normalized = PathUtils.normalize_path(path)
        segs = [seg for seg in normalized.split("/") if seg]
        # Remove Windows drive letter if present (e.g., 'C:')
        if segs and segs[0].endswith(":"):
            segs = segs[1:]
        return segs

    @staticmethod
    def common_prefix(list_of_seg_lists: List[List[str]]) -> List[str]:
        """
        Find common prefix across multiple path segment lists.
        
        Parameters
        ----------
        list_of_seg_lists : List[List[str]]
            List of path segment lists.
            
        Returns
        -------
        List[str]
            Common prefix segments.
        """
        if not list_of_seg_lists:
            return []
        
        prefix: List[str] = []
        min_len = min(len(s) for s in list_of_seg_lists)
        
        for i in range(min_len):
            col = {s[i] for s in list_of_seg_lists}
            if len(col) == 1:
                prefix.append(next(iter(col)))
            else:
                break
        return prefix

    @staticmethod
    def relative_segments(path: str, common_prefix: List[str]) -> List[str]:
        """
        Get relative path segments after removing common prefix.
        
        Parameters
        ----------
        path : str
            Full path.
        common_prefix : List[str]
            Common prefix to remove.
            
        Returns
        -------
        List[str]
            Relative path segments.
        """
        segs = PathUtils.split_segments(path)
        prefix_len = len(common_prefix)
        return segs[prefix_len:] if len(segs) >= prefix_len else segs

    @staticmethod
    def short_path(path: str, keep: int = 3) -> str:
        """
        Create a shortened version of a path.
        
        Parameters
        ----------
        path : str
            Path to shorten.
        keep : int, optional
            Number of trailing segments to keep, by default 3.
            
        Returns
        -------
        str
            Shortened path, or original if shorter than keep.
        """
        normalized = PathUtils.normalize_path(path)
        if not normalized:
            return "(unknown)"
        
        parts = normalized.split("/")
        if len(parts) <= keep:
            return normalized
        return ".../" + "/".join(parts[-keep:])

    @staticmethod
    def short_relative_label(rel_segs: List[str], keep: int = 3) -> str:
        """
        Create a short label from relative path segments.
        
        Parameters
        ----------
        rel_segs : List[str]
            Relative path segments.
        keep : int, optional
            Number of trailing segments to keep, by default 3.
            
        Returns
        -------
        str
            Short label for display.
        """
        if not rel_segs:
            return "(root)"
        if len(rel_segs) <= keep:
            return "/".join(rel_segs)
        return ".../" + "/".join(rel_segs[-keep:])

    @staticmethod
    def anchor_for_file(path: str) -> str:
        """
        Generate a URL-safe anchor ID from a file path.
        
        Parameters
        ----------
        path : str
            File path.
            
        Returns
        -------
        str
            Anchor ID suitable for HTML/Markdown links.
        """
        raw = PathUtils.strip_drive_letter(path).lower()
        slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
        return f"file-{slug or 'unknown'}"

    @staticmethod
    def safe_id(*parts: str) -> str:
        """
        Create a safe identifier from multiple parts.
        
        Parameters
        ----------
        *parts : str
            Parts to join into an identifier.
            
        Returns
        -------
        str
            Safe identifier with only alphanumeric and underscore characters.
        """
        raw = "_".join(parts)
        return re.sub(r"[^a-zA-Z0-9_]", "_", raw)

    @staticmethod
    def matches_glob_pattern(path: str, pattern: str) -> bool:
        """
        Check if a path matches a glob pattern (supports **).
        
        Parameters
        ----------
        path : str
            Path to check.
        pattern : str
            Glob pattern.
            
        Returns
        -------
        bool
            True if path matches pattern.
        """
        normalized = PathUtils.normalize_path(path)
        p = pathlib.PurePosixPath(normalized)
        try:
            return p.match(pattern)
        except Exception:
            return False

    @staticmethod
    def matches_regex_pattern(path: str, pattern: str) -> bool:
        """
        Check if a path matches a regex pattern.
        
        Parameters
        ----------
        path : str
            Path to check.
        pattern : str
            Regex pattern.
            
        Returns
        -------
        bool
            True if path matches pattern.
        """
        normalized = PathUtils.normalize_path(path)
        try:
            return bool(re.search(pattern, normalized))
        except re.error:
            return False
