import pafy
from typing import List, Optional
from pathlib import Path
from collections import namedtuple
import logging
import html
import re
import subprocess
import os

pafy.set_api_key('AIzaSyCwRtNtJFfKTm_s5a8YmRTN1gpdMCiUCFg')
logger = logging.getLogger(__name__)

TitleAndID = namedtuple('TitleAndID', ["title", "id"])

ansi_escape = re.compile(r'''
    \x1B    # ESC
    [@-_]   # 7-bit C1 Fe
    [0-?]*  # Parameter bytes
    [ -/]*  # Intermediate bytes
    [@-~]   # Final byte
''', re.VERBOSE)


class YoutubeMusic:

    @staticmethod
    def gen_qs(query: str):
        qs = {
            'q': query,
            'maxResults': 10,
            'safeSearch': "none",
            'part': 'id,snippet',
            'type': 'video',
            'videoDuration': 'any',
            'key': 'AIzaSyCwRtNtJFfKTm_s5a8YmRTN1gpdMCiUCFg'
        }
        return qs

    @staticmethod
    def you_get_to_dict(text):
        '''text:
        ['site:                YouTube',
        'title:               薛之謙 Joker Xue【笑場 Mocking】HD 高清官方完整版 MV',
        'streams:             # Available quality and codecs',
        '    [ DASH ] ____________________________________',
        '    - itag:          \x1b[7m248\x1b[0m',
        '      container:     webm',
        '      quality:       1920x1080 (1080p)',
        '      size:          74.0 MiB (77549203 bytes)',
        '    # download-with: \x1b[4myou-get --itag=248 [URL]\x1b[0m',
        '''
        lines = text.split('\n')[4:]
        items = list()
        item = dict()
        for line in lines:
            line = line.strip()
            line = ansi_escape.sub("", line)
            k_v = line.split(":")
            if len(k_v) != 2:
                if item:
                    items.append(item)
                item = dict()
                continue
            key, value = k_v
            key = key.strip()
            value = value.strip()
            item[key] = value
        return items

    @staticmethod
    def clean_ydl_cache():
        cache_path = Path(os.environ['HOME']) / ".cache/youtube-dl/youtube-sigfuncs"
        files = cache_path.glob("*")
        [f.unlink() for f in files]

    def __init__(self, down_path: str, ext: str, max_files: int, extra_path: List[str] = None):
        self.cookie_file = Path(__file__).absolute().parent / 'youtube.com_cookies.txt'
        self.down_path = Path(down_path).expanduser()
        self.down_path.mkdir(parents=True, exist_ok=True)
        self.ext = ext
        self.max_files = max_files

        if not extra_path:
            self.path_list = [self.down_path]
        else:
            extra_path = [Path(p) for p in extra_path]
            self.path_list = extra_path + [self.down_path]

    def search(self, key: str, len_limit: int = 0) -> List[TitleAndID]:
        title_ids = list()
        items = list()
        try:
            items = pafy.call_gdata('search', self.gen_qs(key))['items']
        except pafy.GdataError as e:
            print(e)
            logger.info(f"Failed with key: {e}")
        for item in items:
            title = item['snippet']['title']
            video_id = item['id']['videoId']
            if len_limit > 0:
                video = pafy.new(video_id)
                if video.length > len_limit:
                    continue
            title_ids.append(TitleAndID(title, video_id))
        return title_ids

    def download_item(self, title_id: TitleAndID, you_get=False) -> Optional[str]:
        title, video_id = title_id
        title = html.unescape(title)
        title = title.replace('/', '_')
        title = title.replace('(', '_')
        title = title.replace(')', '_')
        title = title.replace(' ', '_')
        title = re.sub('_+', '_', title)
        print('title:', title)
        # py = [p.strip() for p in lazy_pinyin(title)]
        # file_name = '-'.join(py).replace(' ','-') + '.' + self.ext
        file_name = title + '.' + self.ext
        print('file_name:', file_name)
        for p in self.path_list:
            file_path = p.joinpath(file_name)
            if file_path.exists():
                print("file_path:", file_path)
                return Path(file_path)
        file_path = self.down_path.joinpath(file_name)
        if you_get:
            down_url = "https://www.youtube.com/watch?v=" + video_id
            # cmd_info = ["you-get", "-c", str(self.cookie_file), "-i", down_url]
            cmd_info = ["you-get", "-i", down_url]
            print(" ".join(cmd_info))
            output = subprocess.check_output(cmd_info).decode("utf-8")
            items = self.you_get_to_dict(output)
            while items:
                item = items.pop()
                if item["container"] != self.ext:
                    continue
                itag = item["# download-with"].split(" ")[1].split("=")[1]
                print("down name:", file_name)
                cmd_down = [
                    "you-get", "-c", str(self.cookie_file),
                    "-O", title, "-o", str(self.down_path), f"--itag={itag}",
                    "--no-caption", down_url
                ]
                print(cmd_down)
                try:
                    subprocess.check_call(cmd_down)
                    return file_path
                except subprocess.CalledProcessError as e:
                    logger.error(
                        f"Failed to download {title} with itag {itag}: {e}"
                    )
        else:
            if self.ext == 'mp4':
                streams = pafy.new(video_id).streams
            else:
                streams = pafy.new(video_id).audiostreams
            streams = [s for s in streams if s.extension == self.ext]
            for s in streams:
                try:
                    logger.info(f"Trying to download {s} for {title}")
                    s.download(str(file_path))
                    if file_path:
                        return file_path
                    else:
                        file_path = self.download_item(title_id, you_get=True)
                        return file_path
                except Exception as e:
                    logger.info(f"Failed to download {s} for {title}: {e}")
                    file_path = self.download_item(title_id, you_get=True)
                    if file_path:
                        return file_path
                    else:
                        continue
        return None

    def download(self, title_ids: list) -> Optional[str]:
        ''' Try to download video from the first item,
        and return once download is finished successfully'''
        self.clean_ydl_cache()
        file_path = None
        for title_id in title_ids:
            try:
                file_path = self.download_item(title_id)
            except Exception as e:
                print(e)
                try:
                    print("Trying to download with you-get")
                    file_path = self.download_item(title_id, True)
                except Exception as e:
                    print(e)
                    continue
            if file_path:
                file_path.touch()
                self.clean(self.down_path, self.max_files)
                return file_path
        return None

    def clean(self, path, max_num):
        ''' Remove most least accessed file
        '''
        files = sorted(
            path.glob("*.mp4"),
            key=lambda x: x.stat().st_atime
        )
        while len(files) > max_num:
            f = files.pop(0)
            logger.info(f"Removing {f}")
            f.unlink()


if __name__ == '__main__':
    print("Searching...")
    search = YoutubeMusic("~/www/music", 'm4a', 3)
    print("Searching...Done")
    items = search.search("差不多先生")
    print(items)
    print("Downloading...")
    title = search.download(items)
    print(title)
