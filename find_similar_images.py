import argparse
import json
import os
import pickle
from dataclasses import dataclass, asdict
from multiprocessing import Pool, cpu_count
from pathlib import Path
from pprint import pprint

import numpy as np
import psutil
from PIL import Image
from imagehash import ImageHash, phash
from pillow_heif import register_heif_opener, register_avif_opener
from tqdm import tqdm

register_heif_opener()
register_avif_opener()

SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.heif', '.avif', '.heic', '.webp'}


@dataclass(slots=True)
class MatchedPairInfo:
    img1: str
    img2: str
    img1_codec: str
    img2_codec: str
    img1_size: tuple[int, int]
    img2_size: tuple[int, int]
    distance: int


def main():
    args = parse_arguments()
    assert_directories_exist(args.dir1, args.dir2)

    hashes_dir1 = hash_images_in_directory(args.dir1, args.hash_size)
    with open('hashes_dir1.pkl', 'wb') as f:
        pickle.dump(hashes_dir1, f)

    # with open('hashes_dir1.pkl', 'rb') as f:
    #     hashes_dir1 = pickle.load(f)

    hashes_dir2 = hash_images_in_directory(args.dir2, args.hash_size)
    with open('hashes_dir2.pkl', 'wb') as f:
        pickle.dump(hashes_dir2, f)

    similar_images = compare_hashes(hashes_dir1, hashes_dir2, args.distance)
    similar_images.sort(key=lambda x: x.distance)  # Sort by similarity score (Hamming distance)

    write_similar_images_to_file(similar_images, args.output_file)
    print(f"Similar images written to {args.output_file}.json")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Find visually similar images between two directories containing images using perceptual iamge hash.')
    parser.add_argument('--dir1', '-d1', help='First directory to search for images.', type=Path, required=True)
    parser.add_argument('--dir2', '-d2', help='Second directory to search for images.', type=Path, required=True)
    parser.add_argument('--output_file', '-o', help='File to store results of similar images.', type=str, required=True)
    parser.add_argument(
        '--distance', '-d', help='Maximum Hamming distance to consider images as similar.', type=int, default=8
    )
    parser.add_argument('--hash_size', '-hs', help='Hash size for perceptual hashing.', type=int, default=16)
    return parser.parse_args()


def assert_directories_exist(*directories: Path) -> None:
    for directory in directories:
        if not directory.is_dir():
            raise ValueError(f'{directory} is not a valid directory.')


def hash_image(args: tuple[Path, int]) -> tuple[Path, ImageHash | None, float]:
    img_path, hash_size = args
    try:
        with Image.open(img_path) as img:
            img_hash = phash(img, hash_size=hash_size)
            aspect_ratio = img.width / img.height
            return img_path, img_hash, aspect_ratio
    except Exception as e:
        print(f"\nError processing {img_path}: {e}")
        return img_path, None, 0.0


def hash_images_in_directory(directory: Path, hash_size: int) -> dict[Path, tuple[ImageHash, float]]:
    image_hashes = {}
    all_paths = {file for file in directory.rglob('*') if file.is_file()}
    img_paths = [img_path for img_path in all_paths if img_path.suffix.lower() in SUPPORTED_EXTENSIONS]

    pprint(f'Ignored files: {all_paths - set(img_paths)}')

    input_data = [(img_path, hash_size) for img_path in img_paths]
    with Pool(processes=cpu_count()) as pool:
        imap = pool.imap(hash_image, input_data)
        for img_path, img_hash, aspect_ratio in tqdm(imap, total=len(img_paths), desc="Hashing images"):
            if img_hash is not None:
                image_hashes[img_path] = (img_hash, aspect_ratio)
    return image_hashes


def compare_hashes(
        hashes_dir1: dict[Path, tuple[ImageHash, float]],
        hashes_dir2: dict[Path, tuple[ImageHash, float]],
        max_distance: int
) -> list[MatchedPairInfo]:
    paths1 = list(hashes_dir1.keys())
    paths2 = list(hashes_dir2.keys())
    distances = get_hash_differencies(hashes_dir1, hashes_dir2)
    aspect_diffs = get_aspects_differences(hashes_dir1, hashes_dir2)

    similar_mask = (distances < max_distance) & (aspect_diffs < 0.01)
    similar_indices = np.where(similar_mask)

    similar_images = []
    with tqdm(total=np.sum(similar_mask), desc="Collecting similar images") as pbar:
        for i, j in zip(similar_indices[0], similar_indices[1]):
            path1 = str(paths1[i])
            path2 = str(paths2[j])
            distance = int(distances[i, j])

            # Get codec and size info
            with Image.open(path1) as img1, Image.open(path2) as img2:
                codec1 = img1.format.lower() if img1.format else Path(path1).suffix[1:].lower()
                codec2 = img2.format.lower() if img2.format else Path(path2).suffix[1:].lower()
                size1 = (img1.width, img1.height)
                size2 = (img2.width, img2.height)

            pair_info = MatchedPairInfo(
                img1=path1,
                img2=path2,
                img1_codec=codec1,
                img2_codec=codec2,
                img1_size=size1,
                img2_size=size2,
                distance=distance
            )
            similar_images.append(pair_info)
            pbar.update(1)

    return similar_images


def get_hash_differencies(hashes_dir1, hashes_dir2):
    hashes1 = np.array([h[0].hash for h in hashes_dir1.values()], dtype=bool)
    hashes2 = np.array([h[0].hash for h in hashes_dir2.values()], dtype=bool)
    differences = hashes1[:, np.newaxis, :, :] != hashes2[np.newaxis, :, :, :]
    return np.sum(differences, axis=(2, 3), dtype=np.int32)


def get_aspects_differences(hashes_dir1, hashes_dir2):
    aspects1 = np.array([h[1] for h in hashes_dir1.values()], dtype=np.float32)
    aspects2 = np.array([h[1] for h in hashes_dir2.values()], dtype=np.float32)
    return np.abs(aspects1[:, np.newaxis] - aspects2[np.newaxis, :])


def write_similar_images_to_file(similar_images: list[MatchedPairInfo], output_file: str) -> None:
    # Convert MatchedPairInfo objects to dictionaries for JSON serialization
    pairs = [asdict(pair) for pair in similar_images]
    with open(f"{output_file}.json", 'wt', encoding='utf-8') as f:
        json.dump(pairs, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    process = psutil.Process(os.getpid())
    process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    main()
