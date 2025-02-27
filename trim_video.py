import numpy as np
import pandas as pd
import imageio
import os
import subprocess
from multiprocessing import Pool
from itertools import cycle
import warnings
import glob
import time
from tqdm import tqdm
from util import save
from argparse import ArgumentParser
from skimage import img_as_ubyte
from skimage.transform import resize
import datetime
warnings.filterwarnings("ignore")

DEVNULL = open(os.devnull, 'wb')

def download(video_id, args):
    video_path = os.path.join(args.video_folder, video_id + ".mp4")
    subprocess.call([args.youtube, '-f', "''best/mp4''", '--write-auto-sub', '--write-sub',
                     '--sub-lang', 'en', '--skip-unavailable-fragments',
                     "https://www.youtube.com/watch?v=" + video_id, "--output",
                     video_path], stdout=DEVNULL, stderr=DEVNULL)
    return video_path


def run(data):
    video_id, args = data
    if not os.path.exists(os.path.join(args.video_folder, video_id.split('#')[0] + '.mp4')):
       download(video_id.split('#')[0], args)

    if not os.path.exists(os.path.join(args.video_folder, video_id.split('#')[0] + '.mp4')):
       print ('Can not load video %s, broken link' % video_id.split('#')[0])
       return 
    reader = imageio.get_reader(os.path.join(args.video_folder, video_id.split('#')[0] + '.mp4'))
    fps = reader.get_meta_data()['fps']
    inp = os.path.join("youtube-taichi", video_id.split('#')[0] + '.mp4')
    df = pd.read_csv(args.metadata)
    df = df[df['video_id'] == video_id]
    all_chunks_dict = [{'start': df['start'].iloc[j], 'end': df['end'].iloc[j],
                        'bbox': list(map(int, df['bbox'].iloc[j].split('-'))), 'frames':[]} for j in range(df.shape[0])]
    partition = df['partition'].iloc[0]
    ref_height = df['height'].iloc[0]
    ref_width = df['width'].iloc[0]
    partition = df['partition'].iloc[0]
    frame = None
    for i, test in enumerate(reader):
        frame = test
        break
    for entry in all_chunks_dict:
        left, top, right, bot = entry['bbox']
        left = int(left / (ref_width / frame.shape[1]))
        top = int(top / (ref_height / frame.shape[0]))
        right = int(right / (ref_width / frame.shape[1]))
        bot = int(bot / (ref_height / frame.shape[0]))
        h, w = bot - top, right - left
        
        if 'person_id' in df:
            first_part = df['person_id'].iloc[0] + "#"
        else:
            first_part = ""
        first_part = first_part + '#'.join(video_id.split('#')[::-1])
        start = entry['start']/fps
        end = entry['end']/fps
        time = end-start
        start = str(datetime.timedelta(seconds=start))
        path = first_part + '#' + str(entry['start']).zfill(6) + '#' + str(entry['end']).zfill(6) + '.mp4'
        save_path = os.path.join(args.out_folder, partition, path)
    command = f'ffmpeg -i {inp} -ss {start} -t {time} -filter:v "crop={w}:{h}:{left}:{top}" {save_path}'
    subprocess.run(command, shell=True)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--video_folder", default='youtube-taichi', help='Path to youtube videos')
    parser.add_argument("--metadata", default='taichi-metadata-new.csv', help='Path to metadata')
    parser.add_argument("--out_folder", default='taichi-png', help='Path to output')
    parser.add_argument("--format", default='.png', help='Storing format')
    parser.add_argument("--workers", default=1, type=int, help='Number of workers')
    parser.add_argument("--youtube", default='./youtube-dl', help='Path to youtube-dl')
 
    parser.add_argument("--image_shape", default=(256, 256), type=lambda x: tuple(map(int, x.split(','))),
                        help="Image shape, None for no resize")

    args = parser.parse_args()
    if not os.path.exists(args.video_folder):
        os.makedirs(args.video_folder)
    if not os.path.exists(args.out_folder):
        os.makedirs(args.out_folder)
    for partition in ['test', 'train']:
        if not os.path.exists(os.path.join(args.out_folder, partition)):
            os.makedirs(os.path.join(args.out_folder, partition))

    df = pd.read_csv(args.metadata)
    video_ids = set(df['video_id'])
    pool = Pool(processes=args.workers)
    args_list = cycle([args])
    for chunks_data in tqdm(pool.imap_unordered(run, zip(video_ids, args_list))):
        None  
