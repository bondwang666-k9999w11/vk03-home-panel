import ctypes, json, math, os, subprocess, threading, time
from ctypes import wintypes
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from functools import lru_cache

EMPTY = dict(cpu_temp=None,gpu_temp=None,cpu_usage=None,gpu_usage=None,memory_usage=None,memory_used=None,memory_total=None)
class Memory(ctypes.Structure):
    _fields_=[('length',wintypes.DWORD),('load',wintypes.DWORD)]+[(n,ctypes.c_ulonglong) for n in ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]

def cpu_temperature(root, now=None):
    try:
        data=json.loads((Path(root)/'vk03_cpu_sensor.json').read_text(encoding='utf-8-sig'))
        age=(time.time() if now is None else now)-float(data['timestamp'])
        value=float(data['cpu_temp'])
        if 0<=age<=5 and math.isfinite(value) and 0<value<=130 and not data.get('error'):return value
    except (OSError,ValueError,KeyError,TypeError):pass
    return None

class PCMonitor:
    def __init__(self,root):
        self.root=root;self.values=EMPTY.copy();self.lock=threading.Lock();self.stop=threading.Event();self.previous=None
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.thread=threading.Thread(target=self.run,name='PC-monitor',daemon=True)
    def start(self):self.thread.start()
    def snapshot(self):
        with self.lock:return self.values.copy()
    def close(self):self.stop.set();self.thread.join(3) if self.thread.is_alive() else None
    def collect(self):
        values=EMPTY.copy();idle=ctypes.c_ulonglong();kernel=ctypes.c_ulonglong();user=ctypes.c_ulonglong()
        if self.kernel.GetSystemTimes(ctypes.byref(idle),ctypes.byref(kernel),ctypes.byref(user)):
            current=(idle.value,kernel.value+user.value)
            if self.previous:
                total=current[1]-self.previous[1]
                if total>0:values['cpu_usage']=round(max(0,min(100,100*(1-(current[0]-self.previous[0])/total))),1)
            self.previous=current
        memory=Memory();memory.length=ctypes.sizeof(memory)
        if self.kernel.GlobalMemoryStatusEx(ctypes.byref(memory)):
            values.update(memory_usage=memory.load,memory_used=(memory.total-memory.available)/2**30,memory_total=memory.total/2**30)
        values['cpu_temp']=cpu_temperature(self.root)
        try:
            smi=Path('C:/Windows/System32/nvidia-smi.exe')
            result=subprocess.run([str(smi),'--query-gpu=temperature.gpu,utilization.gpu','--format=csv,noheader,nounits','--id=0'],capture_output=True,text=True,timeout=2,creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode==0:
                fields=result.stdout.strip().splitlines()[0].split(',')
                for key,field,maximum in zip(('gpu_temp','gpu_usage'),fields,(130,100)):
                    try:
                        value=float(field.strip())
                        if math.isfinite(value) and 0<=value<=maximum:values[key]=value
                    except ValueError:pass
        except (OSError,subprocess.TimeoutExpired,IndexError):pass
        return values
    def run(self):
        while not self.stop.is_set():
            started=time.monotonic()
            try:values=self.collect()
            except Exception:values=EMPTY.copy()
            with self.lock:self.values=values
            try:
                target=Path(self.root)/'vk03_pc_sensor.json'
                temporary=target.with_suffix('.pending.json')
                temporary.write_text(json.dumps(dict(timestamp=time.time(),values=values)),encoding='utf-8')
                os.replace(temporary,target)
            except OSError:pass
            self.stop.wait(max(.05,1-(time.monotonic()-started)))

@lru_cache(maxsize=8)
def monitor_bold_font(size):
    for name in ('msyhbd.ttc','segoeuib.ttf','arialbd.ttf'):
        try:return ImageFont.truetype(str(Path('C:/Windows/Fonts')/name),size)
        except OSError:pass
    return None

def draw_monitor(image,stats,load_font,settings,now=None):
    now=now or datetime.now();draw=ImageDraw.Draw(image)
    color=settings.get('font_color') or '#EAFBFF'
    small=monitor_bold_font(17) or load_font(17);value_font=monitor_bold_font(29) or load_font(29);clock=monitor_bold_font(36) or load_font(36)
    glyphs=Image.new("RGBA",image.size,(0,0,0,0));glyph_draw=ImageDraw.Draw(glyphs)
    def text(x,y,value,font=small,anchor='la'):
        glyph_draw.text((x,y),value,font=font,fill=color,anchor=anchor)
    def value(key,unit):
        v=stats.get(key)
        return '--' if v is None else f'{v:.0f}{unit}'
    for x,key,label in [(18,'cpu','CPU'),(155,'gpu','GPU')]:
        text(x,17,label+' TEMP');text(x+17,45,value(key+'_temp','°C'),value_font)
        text(x,98,label+' USAGE');text(x+17,126,value(key+'_usage','%'),value_font)
    text(942,14,now.strftime('%H:%M:%S'),clock,'ra')
    text(942,62,now.strftime('%Y-%m-%d')+'  '+['周一','周二','周三','周四','周五','周六','周日'][now.weekday()],small,'ra')
    box=(824,192,942,310);usage=stats.get('memory_usage')
    draw.arc(box,135,405,fill=(255,255,255,75),width=7)
    if usage is not None:draw.arc(box,135,135+270*max(0,min(100,usage))/100,fill='#63E4B0',width=7)
    text(883,224,value('memory_usage','%'),value_font,'ma');text(883,264,'内存',small,'ma')
    used,total=stats.get('memory_used'),stats.get('memory_total')
    text(942,321,'-- GB' if used is None or total is None else f'{used:.1f} / {total:.1f} GB',small,'ra')
    glow=glyphs.filter(ImageFilter.GaussianBlur(2.2))
    glow.putalpha(glow.getchannel('A').point(lambda alpha:round(alpha*0.45)))
    image.alpha_composite(glow)
    image.alpha_composite(glyphs)
    return image


def shared_stats(root):
    try:
        data=json.loads((Path(root)/'vk03_pc_sensor.json').read_text(encoding='utf-8'))
        if not 0<=time.time()-float(data['timestamp'])<=5:return EMPTY.copy()
        values=EMPTY.copy()
        for key in values:
            value=data['values'].get(key)
            if isinstance(value,(int,float)) and math.isfinite(value) and value>=0:values[key]=value
        return values
    except (OSError,ValueError,KeyError,TypeError):return EMPTY.copy()
