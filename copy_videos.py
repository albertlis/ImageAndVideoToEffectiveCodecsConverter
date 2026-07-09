"""
copy_videos.py – Step 1 of the HandBrake workflow.

Recursively scans *src_path* for video files and copies them all into a
single flat directory *flat_path* (no sub-folders).  A JSON mapping file
``file_mapping.json`` is written to *flat_path* so that the original
directory tree can be fully restored later with ``restore_videos.py``.

Mapping format::

    {
      "flat_filename.mp4": "relative/original/path.mp4",
      ...
    }

The flat filename is guaranteed to be unique – collisions are resolved by
appending ``_1``, ``_2``, … before the extension.
"""

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import filetype
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    MofNCompleteColumn,
)

from logger_config import get_logger
from timestamps import copy_timestamps

logger = get_logger(__name__)

MAPPING_FILENAME = "file_mapping.json"


# Derive the video-extension whitelist directly from filetype's registered
# matchers so it stays in sync with the library without any manual curation.
_VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    f".{t.extension}" for t in filetype.types if t.mime.startswith("video/")
)


def is_video_file(file_path: Path) -> bool:
    """Return True if *file_path* is a video.

    Two-stage check for performance:
    1. Extension whitelist  – free (no file I/O beyond the directory scan).
    2. filetype magic-bytes – only for files whose extension matched, to
       guard against misnamed files and skip false positives.
    """
    if file_path.suffix.lower() not in _VIDEO_EXTENSIONS:
        return False
    kind = filetype.guess(str(file_path))
    return kind is not None and kind.mime.startswith("video/")


DURATION_TOLERANCE_S = 1.0  # seconds – treat as duplicate if durations differ less than this


def get_duration(file_path: Path) -> float:
    """Return video duration in seconds via ffprobe. Raises RuntimeError on failure."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        raise RuntimeError("ffprobe not found – make sure ffmpeg is installed and in PATH.")

    if result.returncode != 0:
        raise RuntimeError(
            f"ffprobe failed for '{file_path}' "
            f"(exit {result.returncode}): {result.stderr.strip()}"
        )
    raw = result.stdout.strip()
    if not raw:
        raise RuntimeError(f"ffprobe returned empty duration for '{file_path}'")
    return float(raw)


def find_stem_collision(dst_dir: Path, filename: str) -> Path | None:
    """Return an existing *video* file in *dst_dir* that shares the stem but
    has a different extension, or None if no such file exists."""
    stem = Path(filename).stem
    suffix = Path(filename).suffix.lower()
    for existing in dst_dir.iterdir():
        if (
            existing.is_file()
            and existing.stem == stem
            and existing.suffix.lower() != suffix
            and existing.suffix.lower() in _VIDEO_EXTENSIONS
        ):
            return existing
    return None


def unique_flat_path(dst_dir: Path, filename: str) -> Path:
    """Return a path inside *dst_dir* that does not yet exist.

    If *filename* is already taken the stem gets a numeric suffix:
    ``video.mp4`` → ``video_1.mp4`` → ``video_2.mp4`` …
    """
    candidate = dst_dir / filename
    if not candidate.exists():
        return candidate
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while True:
        candidate = dst_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def collect_videos(src_path: Path) -> list[Path]:
    logger.info(f"Scanning [bold]{src_path}[/bold] for video files …")
    videos = [f for f in src_path.rglob("*") if f.is_file() and is_video_file(f)]
    logger.info(f"Found [green]{len(videos)}[/green] video file(s).")
    return videos


def copy_videos(src_path: Path, flat_path: Path) -> None:
    flat_path.mkdir(parents=True, exist_ok=True)

    videos = collect_videos(src_path)
    if not videos:
        logger.warning("No video files found – nothing to do.")
        return

    file_mapping: dict[str, str] = {}

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )

    with progress:
        task = progress.add_task("Copying …", total=len(videos))
        for src_file in videos:
            rel_path = src_file.relative_to(src_path)

            # --- stem-collision check (same name, different extension) ---
            collision = find_stem_collision(flat_path, src_file.name)
            if collision is not None:
                dur_new = get_duration(src_file)
                dur_existing = get_duration(collision)
                existing_rel = file_mapping.get(collision.name, collision.name)

                if abs(dur_new - dur_existing) < DURATION_TOLERANCE_S:
                    # Same content, different container – keep the older file.
                    logger.warning(
                        f"[yellow]Skipping[/yellow] [cyan]{rel_path}[/cyan] "
                        f"– stem collision with [cyan]{existing_rel}[/cyan] "
                        f"(duration ≈ {dur_existing:.1f}s, diff "
                        f"{abs(dur_new - dur_existing):.3f}s < {DURATION_TOLERANCE_S}s). "
                        f"Keeping the already-copied file."
                    )
                    progress.advance(task)
                    continue
                else:
                    logger.info(
                        f"Stem collision for [cyan]{src_file.name}[/cyan] but durations differ "
                        f"(new={dur_new:.1f}s, existing={dur_existing:.1f}s) – treating as distinct file."
                    )
                    # Rename the already-copied colliding file to free the original name,
                    # then let unique_flat_path pick a suffix for the new file.
                    new_collision_path = unique_flat_path(flat_path, collision.name)
                    collision.rename(new_collision_path)
                    old_mapping_value = file_mapping.pop(collision.name)
                    file_mapping[new_collision_path.name] = old_mapping_value
                    logger.debug(
                        f"Renamed existing [yellow]{collision.name}[/yellow] → "
                        f"[yellow]{new_collision_path.name}[/yellow] in flat dir."
                    )

            dst_file = unique_flat_path(flat_path, src_file.name)

            shutil.copy2(src_file, dst_file)
            copy_timestamps(src_file, dst_file)
            file_mapping[dst_file.name] = rel_path.as_posix()
            logger.debug(f"Copied  [cyan]{rel_path}[/cyan] → [yellow]{dst_file.name}[/yellow]")
            progress.advance(task)

    mapping_path = flat_path / MAPPING_FILENAME
    with mapping_path.open("wt", encoding="utf-8") as fh:
        json.dump(file_mapping, fh, indent=2, ensure_ascii=False)

    logger.info(
        f"[bold green]Done.[/bold green] {len(file_mapping)} file(s) copied. "
        f"Mapping saved to [bold]{mapping_path}[/bold]"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Copy video files from a directory tree into a flat directory "
            "for batch processing (e.g. HandBrake).  Saves a mapping file "
            "so the tree can be restored afterwards."
        )
    )
    parser.add_argument(
        "--src_path", "-s",
        type=Path,
        required=True,
        help="Source directory to scan recursively for video files.",
    )
    parser.add_argument(
        "--flat_path", "-f",
        type=Path,
        required=True,
        help="Flat destination directory where all videos will be copied.",
    )
    args = parser.parse_args()

    if not args.src_path.exists():
        logger.error(f"src_path does not exist: {args.src_path.resolve()}")
        raise SystemExit(1)
    if not args.src_path.is_dir():
        logger.error(f"src_path is not a directory: {args.src_path.resolve()}")
        raise SystemExit(1)

    copy_videos(args.src_path, args.flat_path)


if __name__ == "__main__":
    main()
