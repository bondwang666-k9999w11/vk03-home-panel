"""VK03 appearance editor: local preview, no USB or HA access."""
import ast
import json
import math
import os
import shutil
import sys
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
from PIL import Image, ImageDraw, ImageFont, ImageTk, ImageOps
from vk03_theme import Appearance, DEFAULTS, normalize
from vk03_media import VIDEO_SUFFIXES
from vk03_monitor import shared_stats
from vk03_config import demo_bindings, VERSION

ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent


def preview_renderer(root):
    # Read only constants and drawing helpers; never import the USB panel.
    source = (root / 'vk03_home_panel_daily.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    ns = dict(json=json, math=math, queue=queue, threading=threading, time=time,
              APP_DIR=root, PREVIEW_BINDINGS=demo_bindings(), Image=Image, ImageDraw=ImageDraw, ImageFont=ImageFont,
              SCREEN_WIDTH=960, SCREEN_HEIGHT=360, HA_POLL_SECONDS=1)
    for name in ('load_font',):
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'preview', 'exec'), ns)
    for name, size in [('FONT_TITLE',28),('FONT_BUTTON',30),('FONT_STATUS',19),('FONT_SMALL',16),('FONT_TEMP',40)]:
        ns[name] = ns['load_font'](size)
    section = source[source.index('def load_background_color'):source.index('# ENCODE IMAGE FOR MS912C')]
    exec(section.rsplit('# ============================================================',1)[0], ns)
    entities = {e: {'state':'off','attributes':{}} for e in ns['ALL_ENTITIES']}
    for i, e in enumerate(ns['LIGHT_ENTITIES'].values()):
        entities[e]['state'] = 'on' if i % 2 == 0 else 'off'
    entities[ns['AC_ENTITY']] = {'state':'cool', 'attributes':dict(hvac_modes=['cool','dry','fan_only','heat','off'],
        temperature=26, current_temperature=24, supported_features=425,fan_mode='自动',
        fan_modes=['自动','一档','二档','三档'], swing_mode='off',swing_modes=['off','vertical'])}
    entities[ns['PURIFIER_ENTITY']] = {'state':'on','attributes':dict(preset_modes=['自动','睡眠','一档','二档','三档','最爱'],preset_mode='自动',supported_features=57)}
    for key,value,unit in [('temperature','24.4','°C'),('humidity','50','%'),('pm25','12','μg/m³'),('pm10','20','μg/m³')]:
        entities[ns['ENV_ENTITIES'][key]] = {'state':value,'attributes':{'unit_of_measurement':unit}}
    ns.update(snapshot={'entities':entities,'unit':'°C','connection':'online'},
              notice='预览数据 · 保存后应用到 VK03',pending=False,page='home')
    ns["pc_stats"] = shared_stats(root)
    return ns


class Editor:
    def __init__(self, window):
        self.window = window
        window.title('VK03 外观设置')
        window.geometry('1030x850')
        window.minsize(1000, 820)
        self.ns = preview_renderer(ROOT)
        self.theme = self.ns['appearance']
        self.settings = dict(self.theme.settings)
        self.image_path = self.settings['background_image']
        self.opacity = tk.DoubleVar(value=self.settings['button_opacity'])
        self.brightness = tk.DoubleVar(value=self.settings['image_brightness'])
        self.fit = tk.StringVar(value=self.settings['image_fit'])
        self.page = tk.StringVar(value='监控页')
        self.button_mode=tk.StringVar(value=self.settings['button_mode'])
        self.fps = tk.StringVar(value=str(self.settings['animation_fps']))
        self.path_label = tk.StringVar(value=self.image_path or '当前使用纯色背景')
        self.pending_preview = None
        self.save_results=queue.Queue()
        self.saving=False
        outer = ttk.Frame(window, padding=20)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer,text='VK03 外观设置 · v'+VERSION,font=('Microsoft YaHei UI',20,'bold')).pack(anchor='w')
        ttk.Label(outer,text='选择背景图片，调整卡片透明度。预览使用示例数据，不会操作设备。').pack(anchor='w',pady=(5,12))
        ttk.Label(outer,text='监控页与 VK03 共用实时读数；面板未运行或无有效读数时显示 --。').pack(anchor='w')
        self.preview = ttk.Label(outer)
        self.preview.pack()
        controls = ttk.Frame(outer)
        controls.pack(fill='x',pady=12)
        ttk.Button(controls,text='选择背景图片',command=self.choose_image).pack(side='left')
        ttk.Button(controls,text='使用纯色背景',command=self.clear_image).pack(side='left',padx=8)
        ttk.Button(controls,text='选择底色',command=self.choose_color).pack(side='left')
        ttk.Button(controls,text='字体颜色',command=self.choose_font_color).pack(side='left',padx=8)
        combo = ttk.Combobox(controls,textvariable=self.page,values=['监控页','首页','空调','净化器'],state='readonly',width=12)
        combo.pack(side='right');combo.bind('<<ComboboxSelected>>',lambda event:self.schedule_preview())
        ttk.Label(outer,textvariable=self.path_label,wraplength=960).pack(anchor='w')
        sliders = ttk.Frame(outer);sliders.pack(fill='x',pady=8)
        ttk.Label(sliders,text='按钮透明度').grid(row=0,column=0,sticky='w')
        # Display transparency; runtime stores opacity.
        self.transparency = tk.DoubleVar(value=100-self.opacity.get())
        ttk.Scale(sliders,from_=0,to=100,variable=self.transparency,command=lambda value:self.schedule_preview()).grid(row=0,column=1,sticky='ew',padx=12)
        self.transparency_label=ttk.Label(sliders,width=16);self.transparency_label.grid(row=0,column=2)
        ttk.Label(sliders,text='背景亮度').grid(row=1,column=0,sticky='w',pady=8)
        ttk.Scale(sliders,from_=20,to=160,variable=self.brightness,command=lambda value:self.schedule_preview()).grid(row=1,column=1,sticky='ew',padx=12)
        self.brightness_label=ttk.Label(sliders,width=16);self.brightness_label.grid(row=1,column=2)
        ttk.Label(sliders,text='动画帧率').grid(row=2,column=0,sticky='w')
        fps_combo=ttk.Combobox(sliders,textvariable=self.fps,values=['5','10','15','20','30'],state='readonly',width=8)
        fps_combo.grid(row=2,column=1,sticky='w',padx=12,pady=6)
        fps_combo.bind('<<ComboboxSelected>>',lambda event:self.schedule_preview())
        ttk.Label(sliders,text='FPS · 默认 15').grid(row=2,column=2)
        ttk.Label(sliders,text='按钮样式').grid(row=3,column=0,sticky='w')
        modes=ttk.Frame(sliders);modes.grid(row=3,column=1,sticky='w',padx=12,pady=5)
        ttk.Radiobutton(modes,text='浅色',variable=self.button_mode,value='light',command=self.schedule_preview).pack(side='left')
        ttk.Radiobutton(modes,text='深色',variable=self.button_mode,value='dark',command=self.schedule_preview).pack(side='left',padx=18)
        sliders.columnconfigure(1,weight=1)
        bottom=ttk.Frame(outer);bottom.pack(fill='x')
        ttk.Radiobutton(bottom,text='填满屏幕（裁剪）',value='cover',variable=self.fit,command=self.schedule_preview).pack(side='left')
        ttk.Radiobutton(bottom,text='完整显示（留边）',value='contain',variable=self.fit,command=self.schedule_preview).pack(side='left',padx=12)
        self.save_button=ttk.Button(bottom,text='保存并应用',command=self.save)
        self.save_button.pack(side='right')
        ttk.Button(bottom,text='恢复默认预览',command=self.reset).pack(side='right',padx=10)
        self.status=tk.StringVar(value='0% 透明度为实心卡片，100% 为完全透明；文字与图标保持清晰。')
        ttk.Label(outer,textvariable=self.status,wraplength=960).pack(anchor='w',pady=8)
        self.performance=tk.StringVar(value='动态背景在后台解码；卡顿时保留上一帧。')
        ttk.Label(outer,textvariable=self.performance).pack(anchor='w')
        self.redraw()
        self.window.after(200, self.animate_preview)

    def animate_preview(self):
        try:
            success,message=self.save_results.get_nowait()
            self.saving=False;self.save_button.configure(state='normal')
            self.status.set(message)
            if not success:messagebox.showerror('保存失败',message)
        except queue.Empty:pass
        visible = self.window.state() != 'withdrawn'
        if visible and (self.theme.animated or self.theme.content_changed() or
                        (self.page.get() == '监控页' and int(time.time()) != getattr(self,'preview_second',None))):
            self.preview_second=int(time.time())
            self.update_preview()
        if visible:
            if self.theme.media is not None and self.theme.media.error:
                self.status.set(self.theme.media.error)
            try:
                info=json.loads((ROOT/'vk03_performance.json').read_text(encoding='utf-8'))
                self.performance.set(f"实测 {info['fps']} FPS · USB {info['send_ms']} ms/帧 · {info.get('mode','静态')}")
            except (OSError, ValueError, KeyError):pass
        delay=max(10,round(1000/self.theme.settings['animation_fps'])) if visible and self.theme.animated else 200
        self.window.after(delay, self.animate_preview)

    def update_preview(self):
        self.ns['pc_stats']=shared_stats(ROOT)
        frame=self.ns['render_ui']()
        self.photo=ImageTk.PhotoImage(frame)
        self.preview.configure(image=self.photo)

    def choose_font_color(self):
        _, color=colorchooser.askcolor(color=self.settings.get('font_color') or '#29362F', title='选择字体颜色')
        if color:self.settings['font_color']=color;self.schedule_preview()

    def schedule_preview(self):
        if self.pending_preview is not None:self.window.after_cancel(self.pending_preview)
        self.pending_preview=self.window.after(100,self.redraw)

    def redraw(self):
        self.pending_preview=None
        self.settings.update(background_image=self.image_path,button_opacity=100-round(self.transparency.get()),
                             image_brightness=round(self.brightness.get()),image_fit=self.fit.get(),animation_fps=int(self.fps.get()),button_mode=self.button_mode.get())
        self.theme.apply(self.settings)
        self.ns['page']={'监控页':'monitor','首页':'home','空调':'ac','净化器':'purifier'}[self.page.get()]
        self.ns['pc_stats']=shared_stats(ROOT)
        frame=self.ns['render_ui']()
        self.photo=ImageTk.PhotoImage(frame)
        self.preview.configure(image=self.photo)
        self.transparency_label.configure(text=f'{round(self.transparency.get())}% 透明')
        self.brightness_label.configure(text=f'{round(self.brightness.get())}%')
        if self.theme.error:self.status.set(self.theme.error)

    def choose_image(self):
        name=filedialog.askopenfilename(title='选择背景图片',filetypes=[('图片或视频','*.png *.jpg *.jpeg *.webp *.bmp *.gif *.mp4 *.mkv *.mov *.webm *.avi *.m4v'),('所有文件','*.*')])
        if not name:return
        try:
            if Path(name).suffix.lower() not in VIDEO_SUFFIXES:
                with Image.open(name) as img:img.verify()
        except Exception as exc:
            messagebox.showerror('无法读取图片',str(exc));return
        self.image_path=name;self.path_label.set(name);self.schedule_preview()

    def clear_image(self):
        self.image_path='';self.path_label.set('当前使用纯色背景');self.schedule_preview()

    def choose_color(self):
        _,color=colorchooser.askcolor(color=self.settings['background_color'],title='选择背景底色')
        if color:self.settings['background_color']=color;self.schedule_preview()

    def reset(self):
        self.settings=dict(DEFAULTS);self.transparency.set(100-DEFAULTS['button_opacity'])
        self.brightness.set(100);self.fit.set('cover');self.fps.set('15');self.button_mode.set('light');self.clear_image()

    def save(self):
        if self.saving:return
        self.redraw()
        settings=normalize(self.settings)
        source=self.image_path
        self.saving=True;self.save_button.configure(state='disabled')
        self.status.set('正在后台复制素材并保存，面板继续运行…')
        def job():
            try:
                save_files(ROOT,settings,source)
                self.save_results.put((True,'已保存。新版面板约 1 秒后应用；素材已复制到安装目录。'))
            except Exception as exc:self.save_results.put((False,str(exc)))
        threading.Thread(target=job,name='VK03-save',daemon=True).start()


def save_files(root, saved, source):
    root=Path(root)
    saved=dict(saved)
    if source:
        path=Path(source)
        if not path.is_absolute():path=root/path
        tag=str(time.time_ns())
        suffix=path.suffix.lower()
        if suffix in VIDEO_SUFFIXES:
            target=root/f'vk03_background_{tag}{suffix}'
            temporary=root/f'vk03_background_{tag}.pending{suffix}'
            shutil.copyfile(path,temporary);os.replace(temporary,target)
        else:
            with Image.open(path) as image:
                animated=bool(getattr(image,'is_animated',False))
                if not animated:
                    image=ImageOps.exif_transpose(image).convert('RGBA')
                    image.thumbnail((1920,1920),Image.Resampling.LANCZOS)
                    target=root/f'vk03_background_{tag}.png'
                    temporary=root/f'vk03_background_{tag}.pending.png'
                    image.save(temporary);os.replace(temporary,target)
            if animated:
                target=root/f'vk03_background_{tag}.gif'
                temporary=root/f'vk03_background_{tag}.pending.gif'
                shutil.copyfile(path,temporary);os.replace(temporary,target)
        saved['background_image']=target.name
    temporary=root/'vk03_theme.pending.json'
    temporary.write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(temporary,root/'vk03_theme.json')
    # Keep recent imported assets; never delete arbitrary user files.
    imports=sorted((p for p in root.glob('vk03_background_*') if p.stem.removeprefix('vk03_background_').isdigit()),
                   key=lambda p:p.stat().st_mtime_ns,reverse=True)
    for asset in imports[3:]:
        if asset.name==saved.get('background_image'):continue
        try:asset.unlink()
        except OSError:pass  # A decoder may still hold an old file temporarily.
    return saved


if __name__=='__main__':
    window=tk.Tk()
    try:Editor(window)
    except Exception as exc:
        messagebox.showerror('无法启动外观设置',str(exc));window.destroy();raise SystemExit(1)
    window.mainloop()
