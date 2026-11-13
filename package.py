from pathlib import Path
import shutil,json,hashlib,zipfile,sys
root=Path(__file__).resolve().parent;folder=root/'dist-0.2.1/VK03Studio';release=root/'releases/standalone-0.2.1';release.mkdir(parents=True,exist_ok=True)
shutil.copy2(root/'uninstall.exe',folder/'uninstall.exe')
(folder/'studio-package.json').write_text(json.dumps({'packageId':'ef41513d-174c-48d8-9ba6-9d5cc919c87f','version':'0.2.1'}),encoding='utf8')
for name in ['README.md','THIRD_PARTY_NOTICES.txt','LICENSE']:shutil.copy2(root/name,folder/name)
shutil.copytree(root/'licenses',folder/'licenses',dirs_exist_ok=True)
python_license=Path(sys.base_prefix)/'LICENSE.txt'
if python_license.exists():shutil.copy2(python_license,folder/'licenses/Python-LICENSE.txt')
files=[p for p in folder.rglob('*') if p.is_file() and p.name!='files.sha256.json']
for p in files:
 if p.suffix.lower() in ['.node','.jsc'] or 'mythcool' in p.name.lower() or p.name.lower() in ['libusb0.dll','icuuc.dll','icuin.dll','icudt.dll']:raise RuntimeError('Unexpected vendor/environment file: '+str(p))
hashes={p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files};(folder/'files.sha256.json').write_text(json.dumps(hashes,indent=2),encoding='utf8')
portable=release/'VK03Studio-0.2.1-preview-win64.zip'
with zipfile.ZipFile(portable,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in folder.rglob('*'):
  if p.is_file():z.write(p,'VK03Studio/'+p.relative_to(folder).as_posix())
source=release/'VK03Studio-0.2.1-source.zip';source_files=[*root.glob('*.py'),*root.glob('*.cs'),*root.glob('build_*.ps1'),root/'VK03Studio.spec',root/'requirements.txt',root/'README.md',root/'README.en.md',root/'LICENSE',root/'THIRD_PARTY_NOTICES.txt',*root.glob('bridge/*'),*root.glob('tests/test_*.py'),*root.glob('tests/test_*.ps1'),*root.glob('tests/fixtures/*'),root/'tests/probe_system.py',*root.glob('docs/**/*'),*root.glob('licenses/**/*'),*root.glob('tools/*.py'),root/'.gitignore',root/'.gitattributes']
with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
 for p in source_files:
  if p.is_file():z.write(p,'VK03Studio-source/'+p.relative_to(root).as_posix())
(release/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in [portable,source]),encoding='ascii')
shutil.copy2(root/'README.md',release/'使用说明.md')
print(json.dumps({'files':len(hashes),'zipMB':round(portable.stat().st_size/1048576,1),'sourceKB':round(source.stat().st_size/1024,1),'vendorRuntimeIncluded':False}))
