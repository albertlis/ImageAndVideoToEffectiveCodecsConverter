import argparse
import os
import shutil
from pathlib import Path
from multiprocessing import Pool

import psutil
from PIL import Image
from tqdm import tqdm

from pillow_heif import register_heif_opener
register_heif_opener()

def get_supported_extensions() -> frozenset[str]:
    """Return all extensions PIL can open, derived from its registered formats."""
    Image.init()  # ensure all format plugins are loaded
    return frozenset(
        ext.lower()
        for ext, fmt in Image.registered_extensions().items()
        if fmt in Image.OPEN
    )


def convert_single_image(task: tuple[Path, Path, str, int]) -> tuple[bool, str]:
    img_path, save_path, codec, quality = task
    try:
        if save_path.exists():
            return True, str(img_path)

        save_path.parent.mkdir(parents=True, exist_ok=True)

        # Same format – just copy
        if img_path.suffix.lower() == f'.{codec}':
            shutil.copy2(img_path, save_path)
            return True, str(img_path)

        with Image.open(img_path) as img:
            # Preserve EXIF when available
            exif = img.info.get('exif')
            save_kwargs: dict = {'quality': quality}
            if exif:
                save_kwargs['exif'] = exif
            img.save(save_path, **save_kwargs)

        # Preserve file timestamps
        shutil.copystat(img_path, save_path)
        return True, str(img_path)
    except Exception as exc:
        return False, f'{img_path}: {exc}'


def build_tasks(
    src_dir: Path,
    dst_dir: Path,
    codec: str,
    quality: int,
) -> list[tuple[Path, Path, str, int]]:
    supported = get_supported_extensions()
    tasks = []
    for img_path in src_dir.rglob('*'):
        if img_path.is_file() and img_path.suffix.lower() in supported:
            relative = img_path.relative_to(src_dir)
            save_path = dst_dir / relative.with_suffix(f'.{codec}')
            tasks.append((img_path, save_path, codec, quality))
    return tasks


def convert_images_in_dir(args: argparse.Namespace) -> None:
    src_dir: Path = args.input_dir.resolve()
    assert src_dir.exists(), f'input_dir does not exist: {src_dir}'
    assert src_dir.is_dir(), f'input_dir is not a directory: {src_dir}'

    if args.output_dir is None:
        dst_dir = src_dir.parent / f'{src_dir.name}_{args.codec}'
    else:
        dst_dir = args.output_dir.resolve()

    dst_dir.mkdir(parents=True, exist_ok=True)

    print(f'Scanning {src_dir} …')
    tasks = build_tasks(src_dir, dst_dir, args.codec, args.quality)
    print(f'Found {len(tasks)} image(s) to process → {dst_dir}')

    errors: list[str] = []

    with Pool(processes=args.processes) as pool:
        with tqdm(total=len(tasks), desc='Converting', unit='img') as pbar:
            for ok, msg in pool.imap_unordered(convert_single_image, tasks):
                if not ok:
                    errors.append(msg)
                pbar.update(1)

    if errors:
        print(f'\n{len(errors)} error(s):')
        for e in errors:
            print(' ', e)
    else:
        print('All images converted successfully.')


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Convert images to AVIF/HEIC efficiently (Python 3.13)'
    )
    parser.add_argument('--input_dir', '-i', required=True, type=Path,
                        help='Source directory with images')
    parser.add_argument('--output_dir', '-o', default=None, type=Path,
                        help='Output directory (default: <input_dir>_<codec> sibling)')
    parser.add_argument('--codec', '-c', default='avif', choices=['avif', 'heic'],
                        help='Target codec (default: avif)')
    parser.add_argument('--quality', '-q', default=60, type=int,
                        choices=range(101), metavar='[0-100]',
                        help='Quality setting 0-100 (default: 60)')
    parser.add_argument('--processes', '-p', type=int,
                        default=psutil.cpu_count(logical=False) or os.cpu_count() or 1,
                        help='Worker processes (default: physical CPU count)')
    args = parser.parse_args()
    convert_images_in_dir(args)


if __name__ == '__main__':
    main()