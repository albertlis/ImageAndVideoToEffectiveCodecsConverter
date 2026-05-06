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
"""

import argparse
import json
import shutil
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

logger = get_logger(__name__)
console = Console()

MAPPING_FILENAME = "file_mapping.json"


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


def restore_videos(flat_path: Path, hb_output_path: Path, restore_dst_path: Path) -> None:
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

    restore_videos(args.flat_path, args.hb_output_path, args.restore_dst_path)


if __name__ == "__main__":
    main()

