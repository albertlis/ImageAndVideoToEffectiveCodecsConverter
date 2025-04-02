import argparse
import shutil
import subprocess
from pathlib import Path

import filetype
from tqdm import tqdm


def is_video_file(file_path: Path) -> bool:
    # Detect the file type using the filetype library
    kind = filetype.guess(str(file_path))
    if kind is None:
        return False

    return 'video/' in kind.mime


def convert_videos_in_dir(args):
    src_path = args.src_path
    dst_path = args.dst_path

    assert src_path.exists(), f'src_path does not exist: {src_path.resolve()}'
    assert src_path.is_dir(), f'src_path is not a directory: {src_path.resolve()}'

    dst_path.mkdir(parents=True, exist_ok=True)

    # Use rglob to find all files in all subdirectories
    files = list(src_path.rglob('*'))

    for file in tqdm(files, total=len(files)):
        if not file.is_file() or not is_video_file(file):
            print(f'Skipping file: {file}')
            continue

        # Compute the relative path of the video with respect to the source directory
        relative_path = file.relative_to(src_path)
        dst_file = dst_path / relative_path.with_suffix('.mp4')
        dst_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            call_str = (
                f'ffmpeg -i "{file.resolve()}" '
                f'-c:v hevc -global_quality 25 -preset veryslow -fps_mode vfr '
                f'-c:a aac -b:a 64k '
                f'-movflags use_metadata_tags -map_metadata 0 "{dst_file.resolve()}" -y'
            )

            print(f"Executing: {call_str}")
            result = subprocess.run(call_str, shell=False, capture_output=True, text=True)
            print(result.stdout)
            print(result.stderr)

            if result.stderr or result.returncode != 0:
                print(f"Error processing file: {file}")
                exit(-1)

            shutil.copystat(file, dst_file, follow_symlinks=True)
            dst_file.unlink(missing_ok=True)
            shutil.move(dst_file, dst_file)

        except Exception as e:
            print(f"Failed to process {file}: {e}")


def main():
    # p = psutil.Process()
    # p.nice(psutil.IDLE_PRIORITY_CLASS if hasattr(psutil, 'IDLE_PRIORITY_CLASS') else psutil.BELOW_NORMAL_PRIORITY_CLASS)

    parser = argparse.ArgumentParser(
        description='Process video files recursively using Intel Quick Sync for HEVC encoding.')
    parser.add_argument('--src_path', '-s', type=Path, required=True,
                        help='Path to the source directory containing video files.')
    parser.add_argument('--dst_path', '-d', type=Path, required=True,
                        help='Path to the destination directory for output files.')

    args = parser.parse_args()
    convert_videos_in_dir(args)


if __name__ == '__main__':
    main()
