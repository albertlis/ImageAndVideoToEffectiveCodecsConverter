import argparse
import json
import shutil
from pathlib import Path

import filetype
from tqdm import tqdm


def is_video_file(file_path: Path) -> bool:
    # Detect the file type using the filetype library
    kind = filetype.guess(str(file_path))
    if kind is None:
        return False
    return 'video/' in kind.mime


def main():
    parser = argparse.ArgumentParser(
        description='Process video files recursively using Intel Quick Sync for HEVC encoding.')
    parser.add_argument('--src_path', '-s', type=Path, required=True,
                        help='Path to the source directory containing video files.')
    parser.add_argument('--dst_path', '-d', type=Path, required=True,
                        help='Path to the destination directory for output files.')

    args = parser.parse_args()

    assert args.src_path.exists(), f'src_path does not exist: {args.src_path.resolve()}'
    assert args.src_path.is_dir(), f'src_path is not a directory: {args.src_path.resolve()}'

    args.dst_path.mkdir(parents=True, exist_ok=True)
    files = list(args.src_path.rglob('*'))
    file_mapping = {}

    for file in tqdm(files, total=len(files)):
        if not file.is_file() or not is_video_file(file):
            print(f'Skipping file: {file}')
            continue

        # Create destination path without subdirectories
        dst_file_path = args.dst_path / file.name

        # Prevent overwriting by appending a counter if necessary
        base_name = dst_file_path.stem
        extension = dst_file_path.suffix
        counter = 1
        while dst_file_path.exists():
            dst_file_path = args.dst_path / f"{base_name}_{counter}{extension}"
            counter += 1

        shutil.copy2(file, dst_file_path)
        file_mapping[str(dst_file_path)] = str(file)

    # Save the mapping to a JSON file
    mapping_file_path = args.dst_path / 'file_mapping.json'
    with open(mapping_file_path, 'wt', encoding='utf-8') as f:
        json.dump(file_mapping, f, indent=2, ensure_ascii=False)

    print(f'File copying and mapping completed. Mapping saved to {mapping_file_path}')


if __name__ == '__main__':
    main()
