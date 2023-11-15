import argparse
import shutil
from pathlib import Path

from PIL import Image
from pillow_heif import register_heif_opener
from tqdm import tqdm

register_heif_opener()

supported_extensions = {'.jpg', '.jpeg', '.png'}


def convert_images_in_dir(args: argparse.Namespace):
    src_dir: Path = args.input_dir
    assert src_dir.exists(), f'input_dir does not exist: {src_dir.resolve()}'
    assert src_dir.is_dir(), f'input_dir is not directory: {src_dir.resolve()}'

    dst_path: Path = args.output_dir
    dst_path.mkdir(exist_ok=True)
    files = list(src_dir.iterdir())
    for i, img_path in tqdm(enumerate(files), total=len(files)):
        if (not img_path.is_file()) or (img_path.suffix.lower() not in supported_extensions):
            print(f'Skipping file: {img_path}')
            continue

        save_path = dst_path / f'{img_path.stem}.{args.codec}'
        img = Image.open(img_path)
        img.save(save_path, compression=args.codec, quality=args.quality)
        shutil.copystat(img_path, save_path, follow_symlinks=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Script used to convert png/jpg images to heif/avif')
    parser.add_argument('--input_dir', '-i', help='Path to the directory with images to convert', type=Path,
                        required=True)
    parser.add_argument('--output_dir', '-o', help='Path to the output file', default='output.txt', type=Path,
                        required=True)
    parser.add_argument('--codec', '-c', help='Codec heif or avif', default='heif', type=str, choices=['heif', 'avif'])
    parser.add_argument(
        '--quality', '-q', help='Codec quality setting [0-100]', default=50, type=int, choices=list(range(101))
    )
    args = parser.parse_args()
    convert_images_in_dir(args)
