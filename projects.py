"""Portable, path-safe scheme bundles."""
import zipfile,json,hashlib,copy,shutil,uuid
from pathlib import Path
from model import validate
ALLOWED={'.png','.jpg','.jpeg','.webp','.bmp','.gif','.mp4','.mkv','.mov','.webm','.avi','.m4v'}
def export_bundle(path,doc):
    data=copy.deepcopy(validate(doc));assets={}
    for record,key in [(data,'media')]+[(v,'icon') for v in data['widgets']]:
        if not record[key]:continue
        p=Path(record[key])
        if not p.is_file() or p.suffix.lower() not in ALLOWED:raise ValueError('素材丢失或格式不支持')
        if p.stat().st_size>512*1024*1024:raise ValueError('单个素材请小于512MB')
        digest=hashlib.sha256(p.read_bytes()).hexdigest();name='assets/'+digest+p.suffix.lower();assets[name]=p;record[key]=name
    with zipfile.ZipFile(path,'w',zipfile.ZIP_STORED) as z:
        z.writestr('scene.json',json.dumps(data,ensure_ascii=False))
        for name,p in assets.items():z.write(p,name)
def import_bundle(path,root):
    with zipfile.ZipFile(path) as z:
        entries=z.infolist();names=[v.filename for v in entries]
        if len(entries)>100 or len(set(names))!=len(names) or sum(v.file_size for v in entries)>1024**3:raise ValueError('方案包过大或含重复文件')
        for v in entries:
            if v.filename=='scene.json':continue
            p=Path(v.filename)
            if len(p.parts)!=2 or p.parts[0]!='assets' or p.suffix.lower() not in ALLOWED or '\\' in v.filename or ':' in v.filename or '..' in p.parts:raise ValueError('方案包路径不安全')
        if z.getinfo('scene.json').file_size>1024**2:raise ValueError('方案描述过大')
        data=validate(json.loads(z.read('scene.json')));refs=[(data,'media')]+[(v,'icon') for v in data['widgets']]
        for record,key in refs:
            if record[key] and (record[key] not in names or not record[key].startswith('assets/')):raise ValueError('素材引用无效')
        folder=Path(root)/'imports'/uuid.uuid4().hex;folder.mkdir(parents=True)
        try:
            for record,key in refs:
                if record[key]:
                    old=record[key];target=folder/Path(old).name
                    if not target.exists():
                        with z.open(old) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst)
                    record[key]=str(target)
            return validate(data)
        except Exception:shutil.rmtree(folder);raise
