import sys,unittest,tempfile,json,zipfile,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model import document,validate,widget,save,load,copy_style
from projects import export_bundle,import_bundle
class ModelTests(unittest.TestCase):
 def test_defaults(self):
  for name in ['日常控制','轻量监控','纯背景']:validate(document(name))
 def test_persistence(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
   p=Path(folder)/'scene.json';d=document();d['widgets'][3]['name']='我的时钟';save(p,d);self.assertEqual(load(p),d)
   broken=copy.deepcopy(d);broken['widgets'][0]['w']=float('nan')
   with self.assertRaises(ValueError):save(p,broken)
   self.assertEqual(load(p),d)
 def test_style_preserves_actions(self):
  a=widget('shortcut');b=widget('shutdown');a['w']=160;b['name']='电源';b['target']='C:/example.exe';copy_style(a,b);self.assertEqual(b['w'],160);self.assertEqual(b['name'],'电源');self.assertEqual(b['target'],'C:/example.exe')
 def test_bundle(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
   root=Path(folder);asset=root/'icon.png';asset.write_bytes(b'test-fixture');d=document();d['widgets'][0]['icon']=str(asset);p=root/'sample.vk03';export_bundle(p,d);result=import_bundle(p,root);self.assertEqual(Path(result['widgets'][0]['icon']).read_bytes(),b'test-fixture')
   with zipfile.ZipFile(root/'bad.vk03','w') as z:z.writestr('../outside.png','bad');z.writestr('scene.json',json.dumps(d))
   with self.assertRaises(ValueError):import_bundle(root/'bad.vk03',root)
if __name__=='__main__':unittest.main()
