"""
restore_videos.py – Step 3 of the HandBrake workflow.

After HandBrake has processed the flat directory produced by ``copy_videos.py``,
this script reads ``file_mapping.json`` and places every converted file into
*restore_dst_path* while mirroring the original directory tree.

Matching is done by **stem** (filename without extension) so format changes
(e.g. ``.mp4`` → ``.mkv``) are handled transparently.

Behaviour on collision (file already exists in *restore_dst_path*):
  - Logs a WARNING and skips the file (original is NOT overwritten).

Summary at the end:
  - ✅  Restored  – copied successfully
  - ⚠️  Skipped   – already exists in destination
  - ❌  Missing   – in mapping but not found in HandBrake output directory

Timestamp preservation (``--src_path``):
  When the original source directory is provided the script:
  1. Embeds the original ``creation_time`` tag into the MP4/MKV container via
     ``ffmpeg -c copy`` (no re-encode) so that Android Gallery / Google Photos
     sort by the correct recording date.
  2. Copies the original file's ``atime`` / ``mtime`` to the restored file.
     On Windows the creation-time (``ctime``) is also restored via the Win32 API.

  The ``creation_time`` tag is read from the original file's container metadata
  first; if missing, the file's ``mtime`` is used as a fallback.
"""

import argparse
import json
import os
import sys
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    MofNCompleteColumn,
)
from rich.table import Table
from rich.console import Console

from logger_config import get_logger
from timestamps import copy_timestamps

logger = get_logger(__name__)
console = Console()

MAPPING_FILENAME = "file_mapping.json"


def get_container_creation_time(path: Path) -> str | None:
    """Return the ``creation_time`` tag from the video container as an ISO 8601
    UTC string (e.g. ``2023-06-15T10:30:00.000000Z``), or *None* if absent or
    unreadable.

    Uses ``ffprobe`` which must be available on PATH.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format_tags=creation_time",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        logger.warning("ffprobe not found – cannot read container creation_time.")
        return None
    except subprocess.TimeoutExpired:
        logger.warning(f"ffprobe timed out reading [cyan]{path.name}[/cyan].")
        return None

    value = result.stdout.strip()
    return value if value else None


def embed_creation_time(dst: Path, iso_ts: str) -> None:
    """Rewrite *dst* in-place using ``ffmpeg -c copy`` with
    ``-metadata creation_time=<iso_ts>``.

    Works for MP4 and MKV without re-encoding.  A temporary file in the same
    directory is used so the final rename is atomic (same volume).
    """
    tmp_path = dst.with_name(f"{dst.stem}_{uuid.uuid4().hex}.tmp{dst.suffix}")
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(dst),
                "-c", "copy",
                "-map_metadata", "0",
                "-metadata", f"creation_time={iso_ts}",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr[-500:] if result.stderr else "unknown error")
        os.replace(tmp_path, dst)
    except Exception as exc:
        logger.warning(
            f"[yellow]Could not embed creation_time into[/yellow] "
            f"[cyan]{dst.name}[/cyan]: {exc}"
        )
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def fix_container_timestamp(original_src_file: Path, dst_file: Path) -> None:
    """Read ``creation_time`` from *original_src_file* and embed it into
    *dst_file*.  Falls back to the original file's ``mtime`` when the tag is
    absent.
    """
    iso_ts = get_container_creation_time(original_src_file)

    if iso_ts is None:
        # Fallback: use mtime of original file, converted to UTC ISO 8601
        mtime = original_src_file.stat().st_mtime
        dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
        iso_ts = dt.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
        logger.debug(
            f"No container creation_time for [cyan]{original_src_file.name}[/cyan] "
            f"– using mtime fallback: {iso_ts}"
        )

    embed_creation_time(dst_file, iso_ts)
    logger.debug(
        f"Embedded creation_time=[green]{iso_ts}[/green] → [yellow]{dst_file.name}[/yellow]"
    )


def load_mapping(flat_path: Path) -> dict[str, str]:
    """Load ``file_mapping.json`` from *flat_path*.

    Returns a dict ``{flat_stem: relative_original_posix_path}``
    keyed by stem (without extension) for format-agnostic matching.
    """
    mapping_path = flat_path / MAPPING_FILENAME
    if not mapping_path.exists():
        logger.error(
            f"Mapping file not found: [bold]{mapping_path}[/bold]\n"
            "Did you run copy_videos.py first?"
        )
        raise SystemExit(1)

    with mapping_path.open("rt", encoding="utf-8") as fh:
        raw: dict[str, str] = json.load(fh)

    # Re-key by stem so we can match regardless of output extension
    by_stem: dict[str, str] = {}
    for flat_name, rel_path in raw.items():
        stem = Path(flat_name).stem
        if stem in by_stem:
            logger.warning(
                f"Duplicate stem [yellow]{stem}[/yellow] in mapping "
                f"([cyan]{flat_name}[/cyan] vs previous entry) – keeping first."
            )
        else:
            by_stem[stem] = rel_path

    logger.info(f"Loaded mapping with [green]{len(by_stem)}[/green] entries.")
    return by_stem


def collect_handbrake_output(hb_output_path: Path) -> dict[str, Path]:
    """Scan HandBrake output directory; return ``{stem: Path}`` mapping."""
    logger.info(f"Scanning HandBrake output: [bold]{hb_output_path}[/bold] …")
    output_files: dict[str, Path] = {}
    for f in hb_output_path.rglob("*"):
        if f.is_file():
            stem = f.stem
            if stem in output_files:
                logger.warning(
                    f"Duplicate stem [yellow]{stem}[/yellow] in HandBrake output "
                    f"([cyan]{f}[/cyan] vs [cyan]{output_files[stem]}[/cyan]) – keeping first."
                )
            else:
                output_files[stem] = f
    logger.info(f"Found [green]{len(output_files)}[/green] file(s) in HandBrake output.")
    return output_files


def restore_videos(
    flat_path: Path,
    hb_output_path: Path,
    restore_dst_path: Path,
    src_path: Path | None = None,
) -> None:
    stem_to_rel = load_mapping(flat_path)
    hb_files = collect_handbrake_output(hb_output_path)

    restored = 0
    skipped: list[str] = []
    missing: list[str] = []

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )

    with progress:
        task = progress.add_task("Restoring …", total=len(stem_to_rel))
        for stem, rel_posix in stem_to_rel.items():
            progress.advance(task)

            if stem not in hb_files:
                logger.warning(
                    f"[red]Missing[/red] in HandBrake output: stem=[yellow]{stem}[/yellow] "
                    f"(original: [cyan]{rel_posix}[/cyan])"
                )
                missing.append(stem)
                continue

            src_file = hb_files[stem]
            # Reconstruct original relative path but use the NEW extension from HandBrake
            original_rel = Path(rel_posix)
            dst_rel = original_rel.with_suffix(src_file.suffix)
            dst_file = restore_dst_path / dst_rel

            if dst_file.exists():
                logger.warning(
                    f"[yellow]Skipped[/yellow] (already exists): [bold]{dst_file}[/bold]"
                )
                skipped.append(str(dst_rel))
                continue

            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)

            # ── Preserve original timestamps + container metadata ──────────
            if src_path is not None:
                original_src_file = src_path / Path(rel_posix)
                if original_src_file.exists():
                    # 1. Fix container creation_time tag (read by Android Gallery)
                    fix_container_timestamp(original_src_file, dst_file)
                    # 2. Fix filesystem atime/mtime/ctime
                    copy_timestamps(original_src_file, dst_file)
                    logger.debug(
                        f"Timestamps + container metadata fixed: [cyan]{original_src_file.name}[/cyan]"
                    )
                else:
                    logger.warning(
                        f"[yellow]Original file not found[/yellow] for timestamp copy: "
                        f"[cyan]{original_src_file}[/cyan] – keeping HandBrake output timestamps."
                    )

            logger.debug(
                f"Restored [cyan]{src_file.name}[/cyan] → [yellow]{dst_rel}[/yellow]"
            )
            restored += 1

    # ── Summary table ──────────────────────────────────────────────────────────
    table = Table(title="Restore summary", show_header=True, header_style="bold magenta")
    table.add_column("Status", style="bold")
    table.add_column("Count", justify="right")
    table.add_row("[green]✅ Restored[/green]", str(restored))
    table.add_row("[yellow]⚠️  Skipped (already exists)[/yellow]", str(len(skipped)))
    table.add_row("[red]❌ Missing in HandBrake output[/red]", str(len(missing)))
    console.print(table)

    if missing:
        logger.warning(
            "Missing stems: " + ", ".join(f"[yellow]{s}[/yellow]" for s in missing)
        )

    # ── Save report file ───────────────────────────────────────────────────────
    if missing or skipped:
        report_path = restore_dst_path / "restore_report.txt"
        with report_path.open("wt", encoding="utf-8") as rh:
            if missing:
                rh.write("=== MISSING in HandBrake output (not converted) ===\n")
                for s in missing:
                    rh.write(f"  {s}\n")
                rh.write("\n")
            if skipped:
                rh.write("=== SKIPPED (already exist in destination) ===\n")
                for s in skipped:
                    rh.write(f"  {s}\n")
        logger.info(f"Report saved to [bold]{report_path}[/bold]")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Restore HandBrake-processed videos to the original directory tree. "
            "Reads file_mapping.json from --flat_path and mirrors the structure "
            "into --restore_dst_path."
        )
    )
    parser.add_argument(
        "--flat_path", "-f",
        type=Path,
        required=True,
        help="Flat directory used during copy_videos.py (contains file_mapping.json).",
    )
    parser.add_argument(
        "--hb_output_path", "-b",
        type=Path,
        required=True,
        help="Directory where HandBrake wrote the converted files.",
    )
    parser.add_argument(
        "--src_path", "-s",
        type=Path,
        required=False,
        default=None,
        help=(
            "Original source directory (the one passed to copy_videos.py). "
            "When provided, the original file's creation_time metadata tag is "
            "embedded into every restored MP4/MKV container (no re-encode) so "
            "Android Gallery / Google Photos sort by the correct recording date. "
            "The file's atime/mtime (and ctime on Windows) are also restored."
        ),
    )
    parser.add_argument(
        "--restore_dst_path", "-r",
        type=Path,
        required=True,
        help="Root of the restored directory tree (mirror of original structure).",
    )
    args = parser.parse_args()

    for name, path in [
        ("flat_path", args.flat_path),
        ("hb_output_path", args.hb_output_path),
    ]:
        if not path.exists():
            logger.error(f"{name} does not exist: {path.resolve()}")
            raise SystemExit(1)
        if not path.is_dir():
            logger.error(f"{name} is not a directory: {path.resolve()}")
            raise SystemExit(1)

    if args.src_path is not None:
        if not args.src_path.exists():
            logger.error(f"src_path does not exist: {args.src_path.resolve()}")
            raise SystemExit(1)
        if not args.src_path.is_dir():
            logger.error(f"src_path is not a directory: {args.src_path.resolve()}")
            raise SystemExit(1)
        logger.info(
            f"Timestamp source: [bold]{args.src_path}[/bold] "
            f"(container creation_time tag + atime/mtime"
            f"{'+ ctime' if sys.platform == 'win32' else ''} will be preserved)"
        )

    restore_videos(args.flat_path, args.hb_output_path, args.restore_dst_path, args.src_path)


if __name__ == "__main__":
    main()

