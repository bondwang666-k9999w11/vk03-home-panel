"""Shared appearance settings. No Home Assistant credentials or USB access."""
import json
import math
import time
from pathlib import Path
from PIL import Image, ImageOps

DEFAULTS = dict(background_color='#D6EFE1', background_image='', button_opacity=90,
                image_brightness=100, image_fit='cover', font_color='', animation_fps=15, button_mode='light')


def normalize(data):
    result = dict(DEFAULTS)
    if not isinstance(data, dict):
        return result
    color = data.get('background_color')
    if isinstance(color, str) and len(color) == 7 and color[0] == '#' and all(c in '0123456789abcdefABCDEF' for c in color[1:]):
        result['background_color'] = color
    font = data.get('font_color')
    if isinstance(font, str) and len(font) == 7 and font[0] == '#' and all(c in '0123456789abcdefABCDEF' for c in font[1:]):
        result['font_color'] = font
    if isinstance(data.get('background_image'), str):
        result['background_image'] = data['background_image']
    for key, low, high in [('button_opacity', 0, 100), ('image_brightness', 20, 160), ('animation_fps', 5, 30)]:
        try:
            value = float(data.get(key, result[key]))
            if math.isfinite(value):
                result[key] = max(low, min(high, int(value)))
        except (ValueError, TypeError, OverflowError):
            pass
    if data.get('image_fit') in ('cover', 'contain'):
        result['image_fit'] = data['image_fit']
    if data.get('button_mode') in ('light','dark'):result['button_mode']=data['button_mode']
    return result


def load(root):
    try:
        return normalize(json.loads((Path(root) / 'vk03_theme.json').read_text(encoding='utf-8-sig')))
    except (OSError, ValueError):
        return dict(DEFAULTS)


class Appearance:
    def __init__(self, root):
        self.root = Path(root)
        self.settings = dict(DEFAULTS)
        self.stamp = object()
        self.media = None
        self.media_key = None
        self.observed = None
        self.frame = None
        self.error = ''
        self.refresh(force=True)

    @property
    def animated(self):
        return self.media is not None and self.media.animated

    def apply(self, settings):
        from vk03_media import Media
        self.settings = normalize(settings)
        key = tuple(self.settings[k] for k in ('background_image','background_color','image_brightness','image_fit','animation_fps'))
        if key != self.media_key:
            if self.media is not None:self.media.close()
            self.media_key=key
            self.media=Media(self.root,self.settings) if self.settings['background_image'] else None
            self.frame=Image.new('RGB',(960,360),self.settings['background_color'])
            self.observed=None
            self.error=''

    def close(self):
        if self.media is not None:self.media.close()
        self.media=None
        self.media_key=None

    def refresh(self, force=False):
        path=self.root/'vk03_theme.json'
        try:stamp=(path.stat().st_mtime_ns,path.stat().st_size)
        except OSError:stamp=None
        if not force and stamp==self.stamp:return False
        self.stamp=stamp
        self.apply(load(self.root))
        return True

    def content_changed(self):
        return self.media is not None and not self.animated and self.media.current is not None and self.media.current is not self.observed

    def background(self):
        if self.media is not None:
            image=self.media.frame()
            self.error=self.media.error
            if image is not None:
                self.observed=image
                return image.copy()
        return self.frame.copy()


def card(draw, rect, color, opacity, radius=16):
    """Blend only card surfaces, leaving text and icons opaque."""
    if getattr(draw,'settings',{}).get('button_mode') == 'dark':
        color={(255,255,255):(34,39,37),(232,247,239):(31,66,49),(237,240,239):(43,47,45)}.get(tuple(color),color)
    base = draw._image
    layer = Image.new('RGBA', base.size)
    from PIL import ImageDraw
    overlay = ImageDraw.Draw(layer)
    overlay.rounded_rectangle(rect, radius=radius, fill=(*color, round(opacity * 255 / 100)))
    if base.mode == "RGBA":base.alpha_composite(layer)
    else:base.paste(layer, (0, 0), layer)


class TextDraw:
    """Override text color without recoloring state icons or card backgrounds."""
    def __init__(self, draw, settings):
        self.draw, self.settings = draw, settings
    def __getattr__(self, name):
        return getattr(self.draw, name)
    def text(self, xy, text, *args, **kwargs):
        if self.settings.get('font_color'):
            kwargs['fill'] = self.settings['font_color']
        elif self.settings.get('button_mode') == 'dark':
            fill=kwargs.get('fill')
            if isinstance(fill,tuple):
                if fill in ((27,133,88),(73,143,108)):kwargs['fill']=(108,231,177)
                elif max(fill)-min(fill)<55:kwargs['fill']=(234,242,237) if max(fill)<100 else (173,187,179)
        return self.draw.text(xy, text, *args, **kwargs)
