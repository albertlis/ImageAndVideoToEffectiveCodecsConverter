import datetime
import os
import shutil
from math import log10, sqrt
from pathlib import Path

import numpy as np
from PIL import Image
from pillow_heif import register_heif_opener
from tqdm import tqdm

register_heif_opener()


def pnsr(original: np.ndarray, compressed: np.ndarray) -> float:
    mse = np.mean((original - compressed) ** 2)
    if (mse == 0):  # MSE is zero means no noise is present in the signal .
        # Therefore PSNR have no importance.
        return 100
    max_pixel = 255.0
    return 20 * log10(max_pixel / sqrt(mse))


# def convert():
#     img_1 = Image.open('1.png').convert('RGB')
    # img_1_arr = np.asarray(img_1)
    # img_2 = Image.open('2.png').convert('RGB')
    # img_2_arr = np.asarray(img_2)
    #
    # results = {
    #     'jpeg': defaultdict(dict),
    #     'heif': defaultdict(dict),
    #     'avif': defaultdict(dict)
    # }
    # for compression in ('jpeg', 'heif', 'avif'):
    #     for quality in range(10, 101, 5):
    #         buf1 = BytesIO()
    #         buf2 = BytesIO()
    #         img_1.save(buf1, format=compression, quality=quality)
    #         img_2.save(buf2, format=compression, quality=quality)
    #         img_1_loaded = np.asarray(Image.open(buf1))
    #         img_2_loaded = np.asarray(Image.open(buf2))
    #         pnsr_1 = pnsr(img_1_arr, img_1_loaded)
    #         pnsr_2 = pnsr(img_2_arr, img_2_loaded)
    #         results[compression]['quality'][quality] = (pnsr_1, pnsr_2)
    #         results[compression]['size'][quality] = (buf1.getbuffer().nbytes, buf2.getbuffer().nbytes)
    # with open('results.pkl', 'wb') as f:
    #     pickle.dump(results, f, protocol=pickle.HIGHEST_PROTOCOL)
    # img_1.save('1.avif', quality=60, exif=img_1.info['exif'])
    # shutil.copystat(src, dst, *, follow_symlinks=True)


def convert_images_in_dir(src_dir: Path, dt):
    dst_path = src_dir.with_name(f'{src_dir.name}_heif')
    dst_path.mkdir(exist_ok=True)
    for i, img_path in tqdm(enumerate(list(src_dir.iterdir()))):
        assert img_path.is_file()
        # if img_path.suffix in {'.mp4'}:
        dst = dst_path / f'{i:0=6}{img_path.suffix}'
        shutil.copy(img_path, dst)
            # continue
        dt_epoch = dt.timestamp()
        os.utime(str(dst), (dt_epoch, dt_epoch))
        # save_path = dst_path / f'{img_path.stem}.heif'
        # img = Image.open(img_path)
        # img.save(save_path, compression='heif', quality=45)
        # shutil.copystat(img_path, save_path, follow_symlinks=True)


if __name__ == '__main__':
    src_path = Path(r'D:\Windows\Pulpit\FB images')
    dt = datetime.datetime(2000, 1, 1)
    convert_images_in_dir(src_path, dt)
