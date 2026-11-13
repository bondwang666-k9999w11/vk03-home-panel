"""VK03 Studio document model. No hardware or user-panel imports."""
from pathlib import Path
import json, uuid, math, copy, os

TYPES = {'music': ('媒体控制', 270, 128), 'volume': ('系统音量', 270, 64), 'brightness': ('画面亮度', 270, 64), 'shortcut': ('快捷方式', 104, 104), 'shutdown': ('关机', 104, 104), 'restart': ('重启', 104, 104), 'clock': ('时间日期', 220, 86), 'cpu': ('CPU 占用', 170, 80), 'memory': ('内存占用', 170, 80), 'gpu': ('GPU 占用', 170, 80), 'cpu_temp': ('CPU 温度', 170, 80), 'gpu_temp': ('GPU 温度', 170, 80), 'memory_bar': ('内存 · 条形', 280, 94), 'memory_ball': ('内存 · 水球', 180, 186), 'memory_gauge': ('内存 · 仪表盘', 220, 186), 'text': ('自定义文字', 180, 64)}

MONITOR_TYPES={'cpu','gpu','cpu_temp','gpu_temp'}
MEMORY_TYPES={'memory_bar','memory_ball','memory_gauge'}

def widget(kind, x=32, y=32):
    name, w, h = TYPES[kind]
    return dict(id=uuid.uuid4().hex, type=kind, name=name, x=x, y=y, w=w, h=h, font='Microsoft YaHei', size=20, color='#eef9f5', text_alpha=1.0, show_text=True, opacity=0.76, icon='', icon_alpha=1.0, glow=False, fill_color='#78dfb0' if kind in MEMORY_TYPES else '#a397ec', target='', transparent=kind in MONITOR_TYPES|MEMORY_TYPES or kind in ('volume', 'brightness', 'clock', 'cpu', 'memory', 'text'))

def document(template='日常控制'):
    widgets=[]
    if template=='日常控制':
        widgets=[widget('music',32,36),widget('volume',32,180),widget('brightness',32,258),widget('clock',708,26)]
        for i in range(6):
            v=widget('shortcut',342+i%3*116,82+i//3*120);v['name']='快捷 '+str(i+1);widgets.append(v)
    elif template=='轻量监控':
        widgets=[widget('cpu',30,32),widget('memory',30,124),widget('clock',710,30)]
    return dict(version=1, name=template, fps=30, brightness=100, background='#123a31', media='', fit='cover', background_only=False, widgets=widgets)

def validate(data):
    if not isinstance(data,dict) or data.get('version')!=1: raise ValueError('不支持的方案格式')
    d=copy.deepcopy(data)
    if not isinstance(d.get('widgets'),list) or len(d['widgets'])>80: raise ValueError('组件数量不正确')
    if d.get('fps') not in (15,30): raise ValueError('帧率仅支持15或30')
    if not isinstance(d.get('brightness'),(int,float)) or not 10<=d['brightness']<=100: raise ValueError('亮度范围10–100')
    if d.get('fit') not in ('cover','contain'): raise ValueError('背景填充方式不正确')
    if not isinstance(d.get('background_only'),bool): raise ValueError('纯背景开关不正确')
    def color(v): return isinstance(v,str) and len(v)==7 and v[0]=='#' and all(c in '0123456789abcdefABCDEF' for c in v[1:])
    if not color(d.get('background')): raise ValueError('背景颜色不正确')
    for key in ('name','media'):
        if not isinstance(d.get(key),str) or len(d[key])>2048: raise ValueError('方案字段不正确')
    ids=set()
    for v in d['widgets']:
        if not isinstance(v,dict) or v.get('type') not in TYPES: raise ValueError('未知组件类型')
        if not isinstance(v.get('id'),str) or not v['id'] or v['id'] in ids: raise ValueError('组件编号重复')
        ids.add(v['id'])
        for key,lo,hi in [('x',0,959),('y',0,359),('w',40,960),('h',32,360),('size',10,80),('text_alpha',0,1),('opacity',0,1),('icon_alpha',0,1)]:
            n=v.get(key)
            if isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or not lo<=n<=hi: raise ValueError('组件尺寸或透明度不正确')
        if v['x']+v['w']>960.01 or v['y']+v['h']>360.01: raise ValueError('组件超出屏幕边界')
        v.setdefault('glow',False)
        if not isinstance(v['glow'],bool):raise ValueError('光晕开关不正确')
        v.setdefault('fill_color','#a397ec')
        if not color(v['fill_color']): raise ValueError('滑条颜色不正确')
        if not color(v.get('color')): raise ValueError('文字颜色不正确')
        for key in ('name','font','target','icon'):
            if not isinstance(v.get(key),str) or len(v[key])>2048 or '\x00' in v[key]: raise ValueError('组件内容不正确')
        if not isinstance(v.get('show_text'),bool) or not isinstance(v.get('transparent'),bool): raise ValueError('显示选项不正确')
    return d

def save(path,data):
    d=validate(data);p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8');os.replace(tmp,p)

def load(path):
    return validate(json.loads(Path(path).read_text(encoding='utf8')))

def copy_style(source,target):
    for key in ('w','h','font','size','color','text_alpha','show_text','opacity','transparent'):
        target[key]=copy.deepcopy(source[key])
    target['x']=min(target['x'],960-target['w']);target['y']=min(target['y'],360-target['h'])


def volume_wave_count(value,muted=False):
    if muted or value<=0:return 0
    return 1 if value<=30 else 2 if value<=70 else 3


def copy_monitor_style(source,target):
    if source['type'] not in MONITOR_TYPES or target['type'] not in MONITOR_TYPES:raise ValueError('仅支持CPU/GPU四项监控')
    for key in ('font','size','color','text_alpha','show_text','glow'):
        target[key]=copy.deepcopy(source.get(key,False) if key=='glow' else source[key])
