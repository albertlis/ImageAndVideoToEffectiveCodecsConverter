import argparse
import shutil
from pathlib import Path

import psutil
from PIL import Image
from pillow_heif import register_heif_opener, register_avif_opener
from tqdm import tqdm

register_heif_opener()
register_avif_opener()


def is_image(file_path: Path) -> bool:
    try:
        with Image.open(file_path) as img:
            img.verify()  # Verify if it's an image
        return True
    except (IOError, SyntaxError):
        return False


def convert_images_in_dir(args: argparse.Namespace):
    src_dir: Path = args.input_dir
    assert src_dir.exists(), f'input_dir does not exist: {src_dir.resolve()}'
    assert src_dir.is_dir(), f'input_dir is not directory: {src_dir.resolve()}'

    dst_path: Path = args.output_dir
    dst_path.mkdir(parents=True, exist_ok=True)

    files = list(src_dir.rglob('*'))

    for img_path in tqdm(files, total=len(files)):
        if not img_path.is_file() or not is_image(img_path):
            print(f'Skipping file: {img_path}')
            continue

        relative_path = img_path.relative_to(src_dir)
        save_path = dst_path / relative_path.with_suffix(f'.{args.codec}')

        if img_path.suffix.lower() == f'.{args.codec}':
            shutil.copy2(img_path, save_path)
            print(f'Copied file: {img_path} to {save_path}')
            continue

        save_path.parent.mkdir(parents=True, exist_ok=True)

        with Image.open(img_path) as img:
            img.save(save_path, compression=args.codec, quality=args.quality)
        shutil.copystat(img_path, save_path, follow_symlinks=True)


def main():
    p = psutil.Process()
    p.nice(psutil.IDLE_PRIORITY_CLASS if hasattr(psutil, 'IDLE_PRIORITY_CLASS') else psutil.BELOW_NORMAL_PRIORITY_CLASS)

    parser = argparse.ArgumentParser(description='Script used to convert png/jpg images to heif/avif')
    parser.add_argument('--input_dir', '-i', help='Path to the directory with images to convert', type=Path,
                        required=True)
    parser.add_argument('--output_dir', '-o', help='Path to the output directory', type=Path, required=True)
    parser.add_argument('--codec', '-c', help='Codec heif or avif', default='heif', type=str, choices=['heif', 'avif'])
    parser.add_argument(
        '--quality', '-q', help='Codec quality setting [0-100]', default=50, type=int, choices=list(range(101))
    )
    args = parser.parse_args()
    convert_images_in_dir(args)


if __name__ == '__main__':
    main()
