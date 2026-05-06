# ImageAndVideoToEffectiveCodecsConverter

This repository contains a set of Python utilities for converting images and videos, finding similar images, filtering duplicates, checking file integrity, and comparing images using a GUI application.

## Project Status
Draft. The project is in the early stages of development and may not be fully functional or stable. Features are being added and tested, but there may be bugs or incomplete functionality. Use at your own risk.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
  - [Convert Images](#convert-images)
  - [Convert Videos](#convert-videos)
  - [HandBrake Workflow](#handbrake-workflow)
    - [Step 1 – Copy Videos to Flat Directory](#step-1--copy-videos-to-flat-directory)
    - [Step 2 – Process in HandBrake](#step-2--process-in-handbrake)
    - [Step 3 – Restore Processed Videos](#step-3--restore-processed-videos)
  - [Find Similar Images](#find-similar-images)
  - [Filter Duplicates](#filter-duplicates)
  - [Compare Images Application](#compare-images-application)
  - [Check Files Integrity](#check-files-integrity)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## Overview

This project provides a collection of scripts and a GUI application to handle image and video processing tasks. The main components include:

1. **Image Conversion**: Convert images to efficient formats like HEIF and AVIF.
2. **Video Conversion**: Convert videos to HEVC using FFmpeg with hardware acceleration support.
3. **Video Copying / HandBrake Workflow**: Copy videos to a flat directory, batch-process in HandBrake, restore the original tree in a new location.
4. **Similarity Detection**: Identify and filter visually similar images based on JSON data.
5. **Duplicate Management**: Move duplicate images based on resolution, codec, and file size.
6. **GUI Application**: Visually compare and manage similar image pairs.
7. **Integrity Checking**: Verify the integrity of image and video files.

Supported image formats:

| Format   | Format   | Format | Format |
|:---------|:---------|:-------|:-------|
| **AVIF** | FITS     | JPEG   | PSD    |
| BLP      | FLI      | JPEG2000 | QOI  |
| BMP      | FTEX     | MPEG   | SGI    |
| BUFR     | GBR      | MPO    | SUN    |
| CUR      | GIF      | MSP    | TGA    |
| DCX      | GRIB     | PALM   | TIFF   |
| DDS      | HDF5     | PCD    | WEBP   |
| DIB      | **HEIF** | PCX    | WMF    |
| EPS      | ICNS     | PDF    | XBM    |
| ICO      | IM       | PIXAR  | XPM    |
| IPTC     | PNG      | PPM    |        |

## Features

- **Image Conversion**: Convert images to HEIF or AVIF with customizable quality settings while preserving metadata.
- **Video Conversion**: Use FFmpeg for HEVC encoding with Intel Quick Sync support.
- **Video Copying**: Copy videos to a single directory with a JSON mapping of source-to-destination paths.
- **Video Restore**: Reconstruct the original directory tree in a new location after HandBrake processing.
- **Similarity Detection**: Process images to identify similar images. Results are saved in a JSON file for further processing.
- **Duplicate Filtering**: Automatically move duplicates based on resolution, codec priority (AVIF > HEIF > PNG > Others), and file size.
- **Interactive GUI**: Compare similar image pairs side-by-side, with options to move unwanted images and save progress.
- **File Integrity**: Check image and video files for corruption using Pillow and FFmpeg.

## Installation

Ensure you have Python 3.11 or newer installed. Clone this repository and install the required packages using [Pipenv](https://pipenv.pypa.io/en/latest/):

```bash
git clone https://github.com/yourusername/ImageAndVideoToEffectiveCodecsConverter.git
cd ImageAndVideoToEffectiveCodecsConverter
pipenv install
```

Additional dependencies:
- **FFmpeg**: Required for video conversion and integrity checking. Install it via your package manager (e.g., `apt install ffmpeg` on Ubuntu, `brew install ffmpeg` on macOS).
- **Pillow with HEIF/AVIF support**: Ensure `pillow-heif` is installed (included in Pipenv).
- **Rich**: Used for coloured logging and progress bars (included in Pipenv).

## Usage

### Convert Images

Convert images to HEIF or AVIF formats using `convert_images.py`:

```bash
pipenv run python convert_images.py -i /path/to/input_dir -o /path/to/output_dir -c heif -q 75
```

- `-i`: Path to the input directory containing images.
- `-o`: Path to the output directory for converted images.
- `-c`: Codec to use (`heif` or `avif`).
- `-q`: Quality setting (0-100, default: 50).

### Convert Videos

Convert videos to HEVC using `convert_video.py`:

```bash
pipenv run python convert_video.py -s /path/to/src_dir -d /path/to/dst_dir
```

- `-s`: Source directory containing video files.
- `-d`: Destination directory for converted videos.

---

## HandBrake Workflow

A three-step pipeline for batch-converting a large video collection with HandBrake while preserving the original directory structure.

```
original tree  ──[copy_videos.py]──►  flat dir  ──[HandBrake]──►  hb_output  ──[restore_videos.py]──►  restored tree
```

### Step 1 – Copy Videos to Flat Directory

Recursively scan `src_path` and copy every video into a single flat directory. A `file_mapping.json` file recording the relative original paths is saved alongside the copies.

```bash
pipenv run python copy_videos.py -s /path/to/original_tree -f /path/to/flat_dir
```

- `-s` / `--src_path`: Root of the original directory tree.
- `-f` / `--flat_path`: Flat destination directory (will be created if missing).

Output `file_mapping.json` example:

```json
{
  "holiday_clip.mp4": "2024/Summer/holiday_clip.mp4",
  "holiday_clip_1.mp4": "2023/Archive/holiday_clip.mp4"
}
```

### Step 2 – Process in HandBrake

Open HandBrake, point it at the flat directory and configure your preset (e.g. H.265 / HEVC).  
Set a **separate** output directory – this is your `hb_output_path` in step 3.  
The output filename stem must match the input stem (HandBrake default behaviour).

### Step 3 – Restore Processed Videos

Copy the converted files from the HandBrake output directory into a new directory that mirrors the original tree. Matching is done by **stem** so extension changes (e.g. `.mp4` → `.mkv`) are handled automatically.

```bash
pipenv run python restore_videos.py \
    -f /path/to/flat_dir \
    -b /path/to/hb_output \
    -r /path/to/restored_tree
```

- `-f` / `--flat_path`: Same flat directory used in step 1 (contains `file_mapping.json`).
- `-b` / `--hb_output_path`: Directory where HandBrake wrote the converted files.
- `-r` / `--restore_dst_path`: Root of the new restored tree (created if missing).

**Collision policy**: if a file already exists in `restore_dst_path` it is **skipped** with a warning (originals are never touched).

A summary table is printed at the end:

| Status | Meaning |
|--------|---------|
| ✅ Restored | File copied successfully |
| ⚠️ Skipped | File already exists in destination |
| ❌ Missing | Stem found in mapping but not in HandBrake output |

---

### Find Similar Images

Identify similar images and generate a JSON file (assumed functionality for `find_similar_images.py` based on context):

```bash
pipenv run python find_similar_images.py -d1 /path/to/dir1 -d2 /path/to/dir2 -o similar_images.json -d 5
```

- `-d1`: First directory to search for images.
- `-d2`: Second directory to search for images.
- `-o`: Output JSON file for similar image pairs.
- `-d`: Maximum Hamming distance for similarity (assumed, adjust as per actual script).


### Filter Confident Duplicates

Optional step after finding similar images. 
If images have distance=0, same stem and aspect ratio we can assume they are duplicates.

Filter confident duplicate images from a JSON file using `filter_duplicates.py`:

```bash
pipenv run python filter_confident_duplicates.py -ij input.json -oj filtered.json -mid moved_images -pd /path/to/priority_dir
```

- `-ij`: Input JSON file with image pairs.
- `-oj`: Output JSON file with filtered results.
- `-mid`: Directory for moved duplicates (default: `moved_images`).
- `-pd`: Optional priority directory (images from this directory are kept).

Criteria for keeping an image (if no priority directory):
1. Higher resolution (width × height).
2. Better codec (AVIF > HEIF > PNG > Others).
3. Larger file size if resolution and codec are equal.

### Compare Images Application

Launch the GUI to compare and manage similar images using `compare_images_app.py`:

```bash
pipenv run python compare_images_app.py -ij similar_images.json -oj remaining.json -mid moved_images
```

- `-ij`: Input JSON file with similar image pairs.
- `-oj`: Output JSON file for remaining pairs.
- `-mid`: Directory for moved (deleted) images (default: `moved_images`).

The GUI displays image pairs with:
- Resolution and path info (green highlights the "better" image).
- Distance score (red if > 0).
- Buttons to delete either image or move to the next pair.

### Check Files Integrity

Verify the integrity of image and video files using `files_integrity_check.py`:

```bash
pipenv run python files_integrity_check.py
```

- Prompts for a directory path.
- Checks images with Pillow and videos with FFmpeg.
- Reports any corruption or unsupported files.

## Development

To contribute or experiment, install development dependencies:

```bash
pipenv install --dev
```

Run scripts or use Jupyter notebooks included in the Pipfile for testing.

## Contributing

Contributions are welcome! Fork the repository, make your changes, and submit a pull request. Ensure your code follows the existing style and includes tests where applicable.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
