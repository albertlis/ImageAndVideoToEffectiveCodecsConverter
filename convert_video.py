import shutil
import subprocess
from pathlib import Path

def main():
    dir_name = 'Wrak_Race'
    src_path = Path(rf'F:\Zdjęcia\{dir_name}')
    dst_path = Path(rf'D:\Windows\Pulpit\Zdjęcia\heif\{dir_name}_heif')

    for file in src_path.iterdir():
        if file.suffix.lower() in {'.mp4', '.mov', '.mts'}:
            dst_file = dst_path / f"{file.stem}.mp4"
            # if not dst_file.exists():
            #     dst_file = dst_file.with_stem(dst_file.stem.upper().replace(' ', ''))
            if file.name == 'WP_20170420_21_02_28_Pro.mp4':
                continue
            assert dst_file.exists(), f'{dst_file.resolve()} not exists'
            out_file = dst_file.with_stem(f"{dst_file.stem}_fixed")
            # if not dst_file.exists():
            #     continue
            call_str = f'ffmpeg -i {file.resolve()} -i {dst_file} -map 1 ' \
                       f'-movflags use_metadata_tags -map_metadata 0 -c copy {out_file}'

            print(call_str)
            result = subprocess.run(call_str, shell=True, capture_output=True, text=True)
            print(result.stdout)
            print(result.stderr)
            shutil.copystat(file, out_file, follow_symlinks=True)
            dst_file.unlink()
            shutil.move(out_file, dst_file)

if __name__ == '__main__':
    main()