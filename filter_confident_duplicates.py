import argparse
import json
import os
import shutil
from pathlib import Path


def process_images(json_path: str, output_json_path: str, moved_copies_dir: str, priority_dir: str | None):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    to_move_path = Path(moved_copies_dir)
    to_move_path.mkdir(exist_ok=True)

    moved_files = set()
    filtered_data = []

    for entry in data:
        img1 = entry["img1"]
        img2 = entry["img2"]

        stem1 = Path(img1).stem
        stem2 = Path(img2).stem

        if stem1 == stem2:
            if priority_dir and priority_dir in img1:
                to_move = img2
            elif priority_dir and priority_dir in img2:
                to_move = img1
            else:
                # Get image info for comparison
                res1 = entry["img1_size"][0] * entry["img1_size"][1]
                res2 = entry["img2_size"][0] * entry["img2_size"][1]
                try:
                    size1 = os.path.getsize(img1)
                    size2 = os.path.getsize(img2)
                except Exception as e:
                    print(f"Error processing {img1=}, {img2=}: {e}")
                    continue

                if res1 > res2:
                    to_move = img2
                elif res2 > res1:
                    to_move = img1
                else:
                    # Same resolution, check codec priority (AVIF/HEIF preferred)
                    codec_priority = {'avif': 3, 'heif': 2, 'png': 1}
                    codec1 = entry["img1_codec"]

                    priority1 = codec_priority.get(codec1, -1)
                    codec2 = entry["img2_codec"]
                    priority2 = codec_priority.get(codec2, -1)

                    if priority1 > priority2:
                        to_move = img2
                    elif priority2 > priority1:
                        to_move = img1
                    else:
                        # Same codec, choose by file size (higher stays)
                        to_move = img2 if size1 > size2 else img1

            src_path = Path(to_move)
            if src_path.exists():
                dest_path = to_move_path / src_path.name
                shutil.move(src_path, dest_path)
                print(f"Moved {to_move} to {dest_path}")
                moved_files.add(to_move)
            else:
                print(f"Warning: {to_move} not found, skipping move")
        else:
            filtered_data.append(entry)

    for entry in data:
        if entry["img1"] not in moved_files and entry["img2"] not in moved_files:
            if entry not in filtered_data:
                filtered_data.append(entry)

    filtered_data = sorted(filtered_data, key=lambda x: x["distance"])
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(filtered_data, f, indent=2, ensure_ascii=False)

    print(f"Filtered JSON saved to {output_json_path}")
    print(f"Total moved files: {len(moved_files)}")
    print(f"Files left : {len(filtered_data)}")


def main():
    parser = argparse.ArgumentParser(
        description="Process image pairs from JSON, move duplicates, and save filtered results. "
                    "If no priority directory is specified, the decision to keep an image is based on: "
                    "1) higher resolution (width × height), "
                    "2) better codec (AVIF > HEIF > PNG > Others), "
                    "3) larger file size if resolutions and codecs are equal."
    )
    parser.add_argument("-ij", "--input_json", type=str, required=True, help="Path to the input JSON file")
    parser.add_argument("-oj", "--output_json", type=str, required=True, help="Path to save the filtered JSON")
    parser.add_argument(
        "-mid", "--moved_images_dir", type=str, default="moved_images",
        help="Directory for duplicate images (default: moved_images)"
    )
    parser.add_argument(
        "-pd", "--priority_dir", type=str, default=None,
        help="Directory to prioritize when deciding which image to keep (default: None)"
    )
    args = parser.parse_args()
    process_images(args.input_json, args.output_json, args.moved_images_dir, args.priority_dir)


if __name__ == "__main__":
    main()
