"""Check tracked/public candidate files and relative Markdown links; never prints secrets."""
from pathlib import Path
import subprocess,re,sys
root=Path(__file__).resolve().parents[1]
try:
 out=subprocess.check_output(['git','-c','safe.directory='+root.as_posix(),'ls-files','--cached','--others','--exclude-standard'],cwd=root,text=True,encoding='utf8')
 paths=sorted(set(out.splitlines()))
except Exception:
 paths=[p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and not any(x.startswith('.') or x in {'build','artifacts','releases'} or x.startswith('dist') for x in p.relative_to(root).parts)]
errors=[]
for name in paths:
 p=root/name
 if not p.is_file():continue
 rel=Path(name)
 if p.suffix.lower() in {'.exe','.dll','.jsc','.node','.zip','.log'} or p.name.lower() in {'scene.json','token.txt','vk03_config.json','vk03_theme.json','studio-package.json','grant.json'}:errors.append(name+': runtime/private artifact')
 if any(x in {'original','analysis','logs','.venv','__pycache__'} for x in rel.parts):errors.append(name+': private/developer directory')
 if p.suffix.lower() in {'.py','.md','.ps1','.cs','.txt','.json','.yml','.yaml'}:
  text=p.read_text(encoding='utf-8-sig')
  if re.search(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)',text):errors.append(name+': secret-like content; value omitted')
 if p.suffix.lower()=='.md':
  for link in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',p.read_text(encoding='utf-8-sig')):
   if '://' in link or link.startswith('#'):continue
   dest=(p.parent/link.split('#')[0]).resolve()
   if not dest.exists():errors.append(name+': broken relative link '+link)
if errors:print('\n'.join(errors));sys.exit(1)
print('PASS public tree:',len(paths),'candidate files; no runtime/private artifacts, secret-like strings or broken relative links')
