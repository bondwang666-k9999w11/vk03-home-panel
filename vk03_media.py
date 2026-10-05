"""Bounded background decoding. The display thread never reads media files."""
from bisect import bisect_right
from collections import deque
from pathlib import Path
import subprocess
import threading
import time
from PIL import Image, ImageOps, ImageEnhance

VIDEO_SUFFIXES = {'.mp4', '.mkv', '.mov', '.webm', '.avi', '.m4v'}
FRAME_BYTES = 960 * 360 * 3
CACHE_BYTES = 64 * 1024 * 1024
RESIDENT_FRAME_BYTES = 960 * 360 * 4  # Pillow RGB storage uses four-byte pixel slots.


def fitted(source, settings):
    frame = Image.new('RGB', (960,360), settings['background_color'])
    source = ImageOps.exif_transpose(source).convert('RGBA')
    if settings['image_fit'] == 'cover':
        source = ImageOps.fit(source, frame.size, method=Image.Resampling.LANCZOS)
    else:
        source.thumbnail(frame.size, Image.Resampling.LANCZOS)
    frame.paste(source, ((960-source.width)//2,(360-source.height)//2), source)
    return ImageEnhance.Brightness(frame).enhance(settings['image_brightness']/100)


class Media:
    def __init__(self, root, settings):
        self.root, self.settings = Path(root), dict(settings)
        path = Path(settings['background_image'])
        self.path = path if path.is_absolute() else self.root/path
        self.fps = settings['animation_fps']
        self.queue = deque()
        self.lock = threading.Condition()
        self.stop = threading.Event()
        self.process = None
        self.current = None
        self.animated = self.path.suffix.lower() in VIDEO_SUFFIXES | {'.gif'}
        self.error = ''
        self.frames, self.ends = [], []
        self.started = None
        self.mode = 'loading'
        self.thread = threading.Thread(target=self.decode, name='VK03-media', daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        with self.lock:self.lock.notify_all()
        process = self.process
        if process is not None and process.poll() is None:
            try:process.terminate()
            except OSError:pass
        # Never wait for blocked disk IO on the UI thread.

    def decode(self):
        try:
            if self.path.suffix.lower() not in VIDEO_SUFFIXES:
                with Image.open(self.path) as source:
                    self.animated = bool(getattr(source, 'is_animated', False))
                    if not self.animated:
                        self.current = fitted(source,self.settings)
                        self.mode = 'static'
                        return
                    frames, ends, duration = [], [], 0
                    for index in range(source.n_frames):
                        if self.stop.is_set():return
                        if (len(frames)+1)*RESIDENT_FRAME_BYTES > CACHE_BYTES:break
                        source.seek(index)
                        frame = fitted(source,self.settings)
                        if self.current is None:self.current=frame
                        frames.append(frame)
                        duration += max(20,int(source.info.get('duration',100)))/1000
                        ends.append(duration)
                    else:
                        with self.lock:
                            self.frames,self.ends=frames,ends
                            self.started=time.monotonic()
                            self.mode='cached GIF'
                        return
                    # Long GIF: discard the partial cache and use bounded streaming.
                    del frames, ends
            self.stream()
        except Exception as exc:
            if not self.stop.is_set():
                self.error='背景读取或解码失败：'+type(exc).__name__
                self.mode='error'
                self.animated=False

    def stream(self):
        ffmpeg = self.root/'ffmpeg.exe'
        if not ffmpeg.is_file():raise FileNotFoundError('ffmpeg.exe')
        if self.settings['image_fit']=='cover':
            scale='scale=960:360:force_original_aspect_ratio=increase,crop=960:360'
        else:
            color='0x'+self.settings['background_color'][1:]
            scale='scale=960:360:force_original_aspect_ratio=decrease,pad=960:360:(ow-iw)/2:(oh-ih)/2:color='+color
        command=[str(ffmpeg),'-hide_banner','-loglevel','error','-nostdin',
                 '-threads','2','-filter_threads','1','-stream_loop','-1','-i',str(self.path),
                 '-vf',f'fps={self.fps},'+scale,'-an','-sn','-dn',
                 '-pix_fmt','rgb24','-f','rawvideo','pipe:1']
        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        self.process=process
        if self.stop.is_set():process.terminate()
        capacity=max(3,int(self.fps*3))  # 3 seconds; <= 90 RGB frames at 30 FPS.
        index=0
        try:
            while not self.stop.is_set():
                with self.lock:
                    while len(self.queue)>=capacity and not self.stop.is_set():self.lock.wait(.1)
                if self.stop.is_set():break
                raw=bytearray()
                while len(raw)<FRAME_BYTES and not self.stop.is_set():
                    chunk=process.stdout.read(FRAME_BYTES-len(raw))
                    if not chunk:break
                    raw.extend(chunk)
                if len(raw)!=FRAME_BYTES:
                    if not self.stop.is_set():raise RuntimeError('video decoder ended')
                    break
                frame=Image.frombytes('RGB',(960,360),bytes(raw))
                if self.settings['image_brightness']!=100:
                    frame=ImageEnhance.Brightness(frame).enhance(self.settings['image_brightness']/100)
                with self.lock:
                    self.queue.append((index/self.fps,frame))
                    if self.started is None and len(self.queue)>=self.fps:
                        self.started=time.monotonic()
                        self.mode='buffered stream'
                    self.lock.notify_all()
                index+=1
        finally:
            if process.poll() is None:process.terminate()
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            process.stdout.close()

    def frame(self):
        with self.lock:
            if self.frames:
                elapsed=(time.monotonic()-self.started)%self.ends[-1]
                self.current=self.frames[min(bisect_right(self.ends,elapsed),len(self.frames)-1)]
            elif self.started is not None:
                elapsed=time.monotonic()-self.started
                while self.queue and self.queue[0][0]<=elapsed:
                    _,self.current=self.queue.popleft()
                self.lock.notify_all()
            return self.current

    def diagnostics(self):
        with self.lock:
            return dict(mode=self.mode, buffered_frames=len(self.queue),
                        cached_frames=len(self.frames), error=self.error)
