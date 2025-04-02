import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pillow_heif
from PIL import Image
from tqdm import tqdm

# Register HEIF/AVIF formats with PIL
pillow_heif.register_heif_opener()
pillow_heif.register_avif_opener()


def check_image(file_path: Path):
    """Checks the integrity of an image file using Pillow (PIL)"""
    try:
        with Image.open(file_path) as img:
            img.verify()  # Verify image integrity using Pillow
    except (IOError, SyntaxError) as e:
        print(f"{file_path}: Image verification failed - {e}")


def check_video(file_path: Path):
    """Checks video files (H.264/H.265) using ffmpeg"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", file_path, "-f", "null", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if result.returncode != 0:
            print(f"{file_path}: Video errors:\n{result.stderr.decode()}")
    except Exception as e:
        print(f"{file_path}: Error processing video - {e}")


def process_file(file_path: Path, supported_image_extensions: set[str]):
    """Processes a single file based on its extension"""
    file_extension = file_path.suffix.lower()

    if file_extension in supported_image_extensions:
        check_image(file_path)
    elif file_extension in (".mp4", ".mkv", ".mov"):  # video file extensions
        check_video(file_path)
    else:
        print(f"{file_path}: Unsupported file type.")


def process_files_concurrently(directory: Path, supported_image_extensions: set[str], max_workers: int = 4):
    """Processes files and directories recursively using ThreadPoolExecutor."""
    files_to_process = []

    # Recursively collect all files in the directory and filter by supported extensions
    for file_path in directory.rglob('*'):
        if file_path.is_file() and file_path.suffix.lower() in supported_image_extensions:
            files_to_process.append(file_path)

    # Concurrent execution with ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(process_file, files_to_process)


def process_files(directory: Path, supported_image_extensions: set[str]):
    """Processes files and directories recursively using ThreadPoolExecutor."""
    files_to_process = []

    # Recursively collect all files in the directory and filter by supported extensions
    for file_path in directory.rglob('*'):
        if file_path.is_file() and file_path.suffix.lower() in supported_image_extensions:
            files_to_process.append(file_path)

    for file_path in tqdm(files_to_process):
        process_file(file_path, supported_image_extensions)


def get_supported_image_extensions() -> set[str]:
    """Returns a set of supported image file extensions by Pillow"""
    return set(Image.registered_extensions())


if __name__ == "__main__":
    # Get the directory path from the user
    directory = Path(input("Enter the path to the directory: "))

    assert directory.exists()
    assert directory.is_dir()
    # Fetch supported image extensions
    supported_image_extensions = get_supported_image_extensions()

    # Concurrent processing with 4 threads (you can adjust max_workers)
    # process_files_concurrently(directory, supported_image_extensions, max_workers=os.cpu_count())
    process_files(directory, supported_image_extensions)
