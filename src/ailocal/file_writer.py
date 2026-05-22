"""Extract code blocks from model output and write files with import fixing."""

import os
import re
from pathlib import Path


def _fix_imports(files: list, workdir: str) -> list:
    """Fix common import errors before writing.
    
    Model writes 'from carpeta.archivo import X' when archivo.py
    is in same dir. Detect and strip the directory prefix.
    """
    created_modules = set()
    for fp, _ in files:
        name = fp.replace(".py", "").replace("/", ".")
        created_modules.add(name)
        if "/" in fp:
            bare = fp.split("/")[-1].replace(".py", "")
            created_modules.add(bare)

    fixed = []
    for filepath, content in files:
        if filepath.endswith(".py"):
            def _fix_line(match):
                full = match.group(1)
                parts = full.split(".")
                for i in range(len(parts) - 1, 0, -1):
                    candidate = ".".join(parts[i:])
                    if candidate in created_modules:
                        return f"from {candidate} import"
                return match.group(0)
            content = re.sub(
                r'from\s+([\w.]+)\s+import',
                _fix_line,
                content
            )
        fixed.append((filepath, content))
    return fixed


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
        "python": "py", "javascript": "js", "typescript": "ts",
        "html": "html", "css": "css", "bash": "sh", "shell": "sh",
        "json": "json", "yaml": "yaml", "toml": "toml", "go": "go",
        "rust": "rs", "c": "c", "cpp": "cpp", "java": "java",
        "ruby": "rb", "php": "php",
    }
    return mapping.get(lang.lower(), lang)


def strip_code_blocks(content: str) -> str:
    """Remove code blocks from content for clean display."""
    cleaned = re.sub(r'```\w*:?.*?\n.*?```', '', content, flags=re.DOTALL)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def extract_and_write_files(content: str, workdir: str = ".") -> list[str]:
    """
    Extract code blocks from markdown and write them as files.
    Also fixes common import errors before writing.
    
    Returns list of filenames created.
    """
    files_created = []
    all_files = []  # (filepath, content)

    # Pattern 1: ```lang:path/to/file.py  (preferred format)
    pattern1 = re.compile(r'```(\w+):(.+?)\n(.*?)\n```', re.DOTALL)

    for m in pattern1.finditer(content):
        filepath = m.group(2).strip().lstrip("./")
        filecontent = m.group(3).strip()
        all_files.append((filepath, filecontent))

    # Pattern 2: ### path/to/file.py  followed by ```python
    if not all_files:
        pattern2 = re.compile(
            r'###\s*`?(.+?\.\w+)`?\s*\n.*?```(\w+)\n(.*?)```', re.DOTALL
        )
        for m in pattern2.finditer(content):
            filepath = m.group(1).strip().lstrip("./")
            filecontent = m.group(3).strip()
            all_files.append((filepath, filecontent))

    # Pattern 3: Just ```python blocks (fallback, numbered)
    if not all_files:
        pattern3 = re.compile(r'```(\w+)\n(.*?)```', re.DOTALL)
        matches = pattern3.findall(content)
        for i, (lang, code) in enumerate(matches):
            ext = _ext_from_lang(lang)
            filepath = f"output_{i+1}.{ext}"
            all_files.append((filepath, code.strip()))

    # Post-process: fix imports BEFORE writing
    all_files = _fix_imports(all_files, workdir)

    # Write all files
    for filepath, filecontent in all_files:
        _write_file(workdir, filepath, filecontent)
        files_created.append(filepath)

    return files_created
