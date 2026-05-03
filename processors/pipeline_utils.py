import json
import os
import tempfile
from pathlib import Path
from typing import Any


def safe_json_write(path: Path, data: Any) -> Path:
    """Atomically write JSON data to *path* using a temp file + os.replace().

    The temporary file is created in the same directory as *path*,
    set to permissions ``0o644`` on Linux, and moved into place with
    ``os.replace()`` so the operation is atomic.  If any exception occurs,
    the temp file is removed and the exception is re-raised.

    Args:
        path: Destination path for the JSON file.
        data: Python object to serialise as JSON.

    Returns:
        The final *path*.

    Raises:
        OSError: If the temp file cannot be written or moved.
        TypeError: If *data* is not JSON serialisable.
    """
    path = Path(path)
    tmp_fd, tmp_path_str = tempfile.mkstemp(dir=path.parent, prefix=".tmp_")
    tmp_path = Path(tmp_path_str)
    try:
        os.write(tmp_fd, json.dumps(data, indent=2).encode("utf-8"))
        os.close(tmp_fd)
        if os.name == "posix":
            os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.close(tmp_fd)
        except OSError:
            pass
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    return path


def safe_text_write(path: Path, content: str) -> Path:
    """Atomically write text to *path* using a temp file + os.replace().

    The temporary file is created in the same directory as *path*,
    set to permissions ``0o644`` on Linux, and moved into place with
    ``os.replace()`` so the operation is atomic.  If any exception occurs,
    the temp file is removed and the exception is re-raised.

    Args:
        path: Destination path for the text file.
        content: String content to write.

    Returns:
        The final *path*.

    Raises:
        OSError: If the temp file cannot be written or moved.
    """
    path = Path(path)
    tmp_fd, tmp_path_str = tempfile.mkstemp(dir=path.parent, prefix=".tmp_")
    tmp_path = Path(tmp_path_str)
    try:
        os.write(tmp_fd, content.encode("utf-8"))
        os.close(tmp_fd)
        if os.name == "posix":
            os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.close(tmp_fd)
        except OSError:
            pass
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    return path


def validate_raw_event(raw: dict) -> dict:
    """Validate a raw event dictionary contains the required keys.

    Required keys:
      - ``chain``
      - ``category``
      - ``description``
      - ``source``
      - ``reliability``

    If ``reliability`` is a string that can be parsed as a float it is
    coerced in-place.  If any required key is missing or ``reliability``
    cannot be coerced to a float, a :exc:`ValueError` is raised.

    Args:
        raw: Dictionary representing a raw event.

    Returns:
        The validated (and possibly coerced) dictionary.

    Raises:
        ValueError: If a required key is missing or ``reliability`` is invalid.
    """
    required = ("chain", "category", "description", "source", "reliability")
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"Missing required key(s): {', '.join(missing)}")

    try:
        raw["reliability"] = float(raw["reliability"])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid reliability value: {raw['reliability']!r} (must be numeric)"
        ) from exc

    return raw


def memory_pressure_mb() -> float:
    """Return available system memory in megabytes.

    Reads ``/proc/meminfo`` (Linux only).  Falls back to ``float('inf')``
    on non-Linux platforms so the caller never crashes.
    """
    try:
        with open("/proc/meminfo", "r", encoding="ascii") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    available_kb: float = float(line.split()[1])
                    return available_kb / 1024.0
                elif line.startswith("MemFree:"):
                    free_kb: float = float(line.split()[1])
                    return free_kb / 1024.0
    except (FileNotFoundError, ValueError, OSError):
        pass
    return float("inf")


def should_throttle() -> bool:
    """Return ``True`` if available memory is below threshold (from config).

    This acts as a simple back-pressure check, useful on memory-constrained
    devices such as the Steam Deck.

    Returns:
        ``True`` if available memory < configured threshold MB, otherwise ``False``.
    """
    from config.loader import get_pipeline_value
    threshold = get_pipeline_value("pipeline.memory_throttle_mb", 500.0)
    return memory_pressure_mb() < threshold
