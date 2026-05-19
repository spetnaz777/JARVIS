import os
import fnmatch
import time
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger

from config import config


@dataclass
class FileResult:
    path: str
    name: str
    size: int
    modified: float
    file_type: str
    score: float = 0.0

    @property
    def size_human(self) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if self.size < 1024:
                return f"{self.size:.1f} {unit}"
            self.size /= 1024
        return f"{self.size:.1f} TB"

    @property
    def modified_human(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(self.modified))

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "name": self.name,
            "size": self.size_human,
            "modified": self.modified_human,
            "type": self.file_type,
            "score": round(self.score, 3),
        }


class FileManager:
    def __init__(self):
        self._index: dict[str, FileResult] = {}
        self._last_index_time: float = 0
        self._index_ttl: float = 300.0  # 5 minutes

    def _needs_reindex(self) -> bool:
        return (time.time() - self._last_index_time) > self._index_ttl

    def _build_index(self):
        logger.info("Building file index...")
        self._index.clear()
        count = 0

        for search_dir in config.SEARCH_DIRS:
            if not os.path.exists(search_dir):
                continue
            try:
                for root, dirs, files in os.walk(search_dir):
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {
                        "node_modules", "__pycache__", ".git", "AppData", "Windows",
                        "Program Files", "Program Files (x86)",
                    }]

                    for fname in files:
                        try:
                            full_path = os.path.join(root, fname)
                            stat = os.stat(full_path)
                            ext = Path(fname).suffix.lower().lstrip(".")
                            self._index[full_path] = FileResult(
                                path=full_path,
                                name=fname,
                                size=stat.st_size,
                                modified=stat.st_mtime,
                                file_type=ext or "file",
                            )
                            count += 1
                        except (PermissionError, OSError):
                            continue

            except (PermissionError, OSError) as e:
                logger.warning(f"Cannot index {search_dir}: {e}")

        self._last_index_time = time.time()
        logger.info(f"File index built: {count} files")

    def _score_result(self, result: FileResult, query: str) -> float:
        name_lower = result.name.lower()
        query_lower = query.lower()
        score = 0.0

        if name_lower == query_lower:
            score += 10.0
        elif name_lower.startswith(query_lower):
            score += 5.0
        elif query_lower in name_lower:
            score += 3.0
        else:
            words = query_lower.split()
            matches = sum(1 for w in words if w in name_lower)
            score += matches * 1.5

        recency = time.time() - result.modified
        if recency < 86400:
            score += 2.0
        elif recency < 604800:
            score += 1.0

        priority_types = {"pdf", "docx", "xlsx", "pptx", "txt", "py", "js", "ts", "md"}
        if result.file_type in priority_types:
            score += 0.5

        return score

    def search(self, query: str, max_results: int = 20, file_type: Optional[str] = None) -> list[dict]:
        if self._needs_reindex():
            self._build_index()

        query = query.strip()
        if not query:
            return []

        results: list[FileResult] = []

        for path, result in self._index.items():
            if file_type and result.file_type.lower() != file_type.lower():
                continue

            score = self._score_result(result, query)
            if score > 0:
                result.score = score
                results.append(result)

        results.sort(key=lambda r: r.score, reverse=True)
        return [r.to_dict() for r in results[:max_results]]

    def glob_search(self, pattern: str, search_dir: Optional[str] = None) -> list[dict]:
        base_dirs = [search_dir] if search_dir else config.SEARCH_DIRS
        results: list[FileResult] = []

        for base in base_dirs:
            if not os.path.exists(base):
                continue
            try:
                for root, dirs, files in os.walk(base):
                    dirs[:] = [d for d in dirs if d not in {
                        "node_modules", "__pycache__", ".git",
                    }]
                    for fname in files:
                        if fnmatch.fnmatch(fname.lower(), pattern.lower()):
                            full_path = os.path.join(root, fname)
                            try:
                                stat = os.stat(full_path)
                                ext = Path(fname).suffix.lower().lstrip(".")
                                results.append(FileResult(
                                    path=full_path,
                                    name=fname,
                                    size=stat.st_size,
                                    modified=stat.st_mtime,
                                    file_type=ext or "file",
                                    score=1.0,
                                ))
                            except (PermissionError, OSError):
                                continue
            except (PermissionError, OSError):
                continue

        results.sort(key=lambda r: r.modified, reverse=True)
        return [r.to_dict() for r in results[:50]]

    def get_file_info(self, path: str) -> Optional[dict]:
        path = os.path.normpath(path)
        if not os.path.exists(path):
            return None
        try:
            stat = os.stat(path)
            name = os.path.basename(path)
            ext = Path(name).suffix.lower().lstrip(".")
            result = FileResult(
                path=path,
                name=name,
                size=stat.st_size,
                modified=stat.st_mtime,
                file_type=ext or ("directory" if os.path.isdir(path) else "file"),
            )
            return result.to_dict()
        except Exception as e:
            logger.error(f"File info error for {path}: {e}")
            return None

    def invalidate_index(self):
        self._last_index_time = 0


file_manager = FileManager()
