"""Extract code blocks from model output and write files."""

import os
import re
from pathlib import Path


def extract_and_write_files(content: str, workdir: str = ".") -> list[str]:
    """
    Extract code blocks from markdown and write them as files.
    
    Handles multiple formats:
    - ```python:path/to/file.py
    - ### filename.py  followed by ```python
    - ```python (fallback, numbered)
    
    Returns list of filenames created.
    """
    files_created = []

    # Pattern 1: ```lang:path/to/file.py
    pattern1 = re.compile(r'```(\w+):(.+?)\n(.*?)\n```', re.DOTALL)
    remaining = content

    for m in pattern1.finditer(content):
        filepath = m.group(2).strip().lstrip("./")
        filecontent = m.group(3).strip()
        _write_file(workdir, filepath, filecontent)
        files_created.append(filepath)
        remaining = remaining.replace(m.group(0), "", 1)

    # Pattern 2: ### path/to/file.py  followed by ```python
    if not files_created:
        pattern2 = re.compile(
            r'###\s*`?(.+?\.\w+)`?\s*\n.*?```(\w+)\n(.*?)```', re.DOTALL
        )
        for m in pattern2.finditer(content):
            filepath = m.group(1).strip().lstrip("./")
            filecontent = m.group(3).strip()
            _write_file(workdir, filepath, filecontent)
            files_created.append(filepath)
            remaining = remaining.replace(m.group(0), "", 1)

    # Pattern 3: Just ```python blocks without specified paths
    if not files_created:
        pattern3 = re.compile(r'```(\w+)\n(.*?)```', re.DOTALL)
        matches = pattern3.findall(content)
        for i, (lang, code) in enumerate(matches):
            ext = _ext_from_lang(lang)
            filepath = f"output_{i+1}.{ext}"
            _write_file(workdir, filepath, code.strip())
            files_created.append(filepath)

    return files_created


def _write_file(workdir: str, filepath: str, content: str):
    """Write a single file, creating directories as needed."""
    fullpath = os.path.join(workdir, filepath)
    dirpath = os.path.dirname(fullpath)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    with open(fullpath, "w") as f:
        f.write(content)


def _ext_from_lang(lang: str) -> str:
    """Map markdown language tag to file extension."""
    mapping = {
        "python": "py",
        "javascript": "js",
        "typescript": "ts",
        "html": "html",
        "css": "css",
        "bash": "sh",
        "shell": "sh",
        "json": "json",
        "yaml": "yaml",
        "toml": "toml",
        "go": "go",
        "rust": "rs",
        "c": "c",
        "cpp": "cpp",
        "java": "java",
        "ruby": "rb",
        "php": "php",
    }
    return mapping.get(lang.lower(), lang)


def strip_code_blocks(content: str) -> str:
    """Remove code blocks from content for clean display."""
    # Remove ``` blocks with or without path
    cleaned = re.sub(r'```\w*:?.*?\n.*?```', '', content, flags=re.DOTALL)
    # Clean up excessive blank lines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()
