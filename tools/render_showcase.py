"""Render public demo images with real UI helpers, without USB/HA access."""
from pathlib import Path
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image
from vk03_appearance_editor import preview_renderer
from vk03_monitor import draw_monitor


def main():
    target = ROOT / 'docs' / 'images'
    target.mkdir(parents=True, exist_ok=True)
    ns = preview_renderer(ROOT)
    theme = ns['appearance']
    try:
        # Original procedural background: no user media or third-party artwork.
        backdrop = Image.new('RGBA', (960, 360))
        pixels = backdrop.load()
        for y in range(360):
            for x in range(960):
                t = (x / 959 + y / 359) / 2
                pixels[x, y] = (int(16 + 18*t), int(53 + 32*t), int(48 + 29*t), 255)
        stats = dict(cpu_temp=42, gpu_temp=38, cpu_usage=34, gpu_usage=3,
                     memory_usage=46, memory_used=14.7, memory_total=32)
        monitor = draw_monitor(backdrop.copy(), stats, ns['load_font'],
                               dict(font_color='#EAFBFF'), datetime(2026, 10, 5, 18, 42, 31))
        monitor.convert('RGB').save(target / 'monitor.png')
        ns['notice'] = '演示数据 · 请绑定自己的 HA 设备'
        for page, mode, name in [('home', 'light', 'home-light'),
                                 ('home', 'dark', 'home-dark'),
                                 ('ac', 'light', 'climate'),
                                 ('purifier', 'dark', 'purifier')]:
            theme.apply(dict(background_color='#D6EFE1', button_mode=mode,
                             button_opacity=82, font_color=''))
            ns['page'] = page
            ns['_overlay_key'] = None
            ns['render_ui']().convert('RGB').save(target / (name + '.png'))
        print('Rendered 5 demo images; no hardware or network access')
    finally:
        theme.close()


if __name__ == '__main__':
    main()
