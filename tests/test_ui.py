import os,sys,tempfile,unittest,copy,struct,time
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtCore import Qt,QPointF
from PySide6.QtGui import QImage,QColor,QPainter,QFont
from app import Studio,STYLE
from model import widget,document,load,validate,volume_wave_count,MONITOR_TYPES
from device import encode_frame,touch_point,DeviceWorker
APP=QApplication([]);APP.setStyle('Fusion');APP.setStyleSheet(STYLE)
class FakeBridge:
 def __init__(self):self.calls=[]
 def post(self,name,payload=None):self.calls.append((name,payload))
 def close(self):pass
class UITests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.window=Studio(self.folder.name,False);self.window.show();APP.processEvents();self.window.poll.stop();self.window.frame_timer.stop();self.window.bridge=FakeBridge()
 def tearDown(self):
  self.window.quitting=True;self.window.autosave.stop();self.window.player.stop();self.window.tray.hide();self.window.close();self.window.deleteLater();APP.processEvents();self.folder.cleanup()
 def test_editor(self):
  w=self.window;self.assertEqual(w.pages.count(),4);self.assertEqual(len(w.doc['widgets']),10);w.layer_selected(4);w.fields['w'].setValue(150);w.apply_properties();self.assertEqual(w.doc['widgets'][4]['w'],150);w.duplicate();self.assertEqual(len(w.doc['widgets']),11);w.undo();self.assertEqual(len(w.doc['widgets']),10);w.redo();self.assertEqual(len(w.doc['widgets']),11)
  item=w.scene.selectedItems()[0] if w.scene.selectedItems() else w.scene.items()[0];item.setSelected(True);item.setPos(9999,9999);self.assertLessEqual(item.pos().x()+item.v['w'],960);self.assertLessEqual(item.pos().y()+item.v['h'],360)
  w.pure.setChecked(True);self.assertTrue(all(not i.isVisible() for i in w.scene.items()));w.pure.setChecked(False);self.assertTrue(all(i.isVisible() for i in w.scene.items()));w.save_doc();self.assertEqual(load(w.config),w.doc);self.assertEqual(w.bridge.calls,[])
 def test_render_and_export_selection(self):
  w=self.window;w.values.update(volume=45,cpu=23,memory=48,media={'title':'本地测试歌曲'});w.layer_selected(4);image=w.render_frame();self.assertEqual((image.width(),image.height()),(960,360));w.scene.clearSelection();other=w.render_frame();self.assertEqual(bytes(image.constBits()),bytes(other.constBits()))
  out=Path(__file__).resolve().parents[1]/'artifacts';out.mkdir(exist_ok=True);image.save(str(out/'panel-preview.png'));w.layer_selected(4);APP.processEvents();w.grab().save(str(out/'studio-editor.png'));w.show_page(1);APP.processEvents();w.grab().save(str(out/'studio-schemes.png'))
 def test_touch_actions(self):
  w=self.window;w.doc=document('纯背景');volume=widget('volume',20,20);power=widget('shutdown',400,20);restart=widget('restart',520,20);w.doc['widgets']=[volume,power,restart];w.rebuild()
  def tap(v,x=.5,y=.5):
   px=v['x']+x*v['w'];py=v['y']+y*v['h'];w.gesture('down',px,py);w.gesture('up',px,py)
  tap(volume,.6,.7);local=w.values['volume'];w.receive_state({'volume':9});self.assertEqual(w.values['volume'],local);w.tick();self.assertTrue(any(n=='volume.set' for n,p in w.bridge.calls));tap(volume,.94,.2);self.assertEqual(w.bridge.calls[-1][0],'volume.muteToggle')
  tap(power);self.assertFalse(any(n=='system.shutdown' for n,p in w.bridge.calls));tap(power);self.assertEqual(w.bridge.calls[-1],('system.shutdown',{'confirmed':True}));tap(restart);w.power_armed=(restart['id'],time.monotonic()-3);tap(restart);self.assertFalse(any(n=='system.restart' for n,p in w.bridge.calls));tap(restart);self.assertEqual(w.bridge.calls[-1][0],'system.restart')
  w.doc['background_only']=True;before=len(w.bridge.calls);tap(power);tap(power);self.assertEqual(len(w.bridge.calls),before)
 def test_properties_fit_and_fill_colors(self):
  w=self.window;w.layer_selected(1)
  for width,height in [(1120,720),(1440,880)]:
   w.resize(width,height);APP.processEvents();APP.processEvents();viewport=w.property_scroll.viewport();self.assertLessEqual(w.props.width(),viewport.width());self.assertEqual(w.property_scroll.horizontalScrollBar().maximum(),0)
   for child in w.props.findChildren(QWidget,options=Qt.FindChildOption.FindDirectChildrenOnly):
    if child.isVisible():self.assertGreaterEqual(child.geometry().left(),0);self.assertLessEqual(child.geometry().right(),w.props.width(),(child.metaObject().className(),child.geometry(),w.props.width()))
  w.doc=document('纯背景');v=widget('volume',0,0);b=widget('brightness',300,0);v['fill_color']='#ff5500';b['fill_color']='#00dd88';w.doc['widgets']=[v,b];w.values['volume']=100;w.rebuild();image=w.render_frame();self.assertEqual(image.pixelColor(80,44).name(),'#ff5500');self.assertEqual(image.pixelColor(380,44).name(),'#00dd88');w.save_doc();self.assertEqual(load(w.config)['widgets'][0]['fill_color'],'#ff5500')
  old=document();del old['widgets'][0]['fill_color'];self.assertEqual(validate(old)['widgets'][0]['fill_color'],'#a397ec')
 def test_speaker_levels(self):
  self.assertEqual([volume_wave_count(v) for v in [0,1,30,31,70,71,100]],[0,1,1,2,2,3,3]);self.assertEqual(volume_wave_count(100,True),0)
  w=self.window;w.doc=document('纯背景');v=widget('volume',0,0);w.doc['widgets']=[v];w.rebuild();sheet=QImage(1080,96,QImage.Format.Format_RGB888);sheet.fill(QColor('#153b31'));p=QPainter(sheet);font=QFont('Microsoft YaHei');font.setPixelSize(15);p.setFont(font);p.setPen(QColor('#eef9f5'))
  for i,level in enumerate([0,30,70,100]):
   w.values['volume']=level;image=w.render_frame().copy(0,0,270,64);p.drawImage(i*270,28,image);p.drawText(i*270+8,20,str(level)+'%')
  p.end();out=Path(__file__).resolve().parents[1]/'artifacts';out.mkdir(exist_ok=True);sheet.save(str(out/'speaker-levels-011.png'));w.doc=document();w.rebuild();w.layer_selected(1);w.resize(1120,720);APP.processEvents();w.grab().save(str(out/'properties-011-compact.png'))
 def test_monitor_style_and_glow(self):
  w=self.window;w.doc=document('纯背景');w.doc['widgets']=[widget(k,20+i*210,120) for i,k in enumerate(['cpu','gpu','cpu_temp','gpu_temp'])]+[widget('memory',20,240)];w.rebuild();w.layer_selected(0);source=w.doc['widgets'][0];source.update(font='Segoe UI',size=28,color='#8cddff',text_alpha=.8,glow=True)
  layout=[(v['x'],v['y'],v['w'],v['h'],v['name']) for v in w.doc['widgets']];w.reuse_style()
  self.assertEqual(layout,[(v['x'],v['y'],v['w'],v['h'],v['name']) for v in w.doc['widgets']]);self.assertTrue(all(v.get('glow') for v in w.doc['widgets'][:4]));self.assertEqual(w.doc['widgets'][4]['size'],20)
  w.values.update(cpu=53,gpu=40,cpu_temp=None,gpu_temp=41,memory=75,memory_used=24,memory_total=32);on=w.render_frame()
  for v in w.doc['widgets'][:4]:v['glow']=False
  off=w.render_frame();self.assertNotEqual(bytes(on.constBits()),bytes(off.constBits()))
  for v in w.doc['widgets'][:4]:v['glow']=True
  w.save_doc();self.assertTrue(load(w.config)['widgets'][0]['glow'])
 def test_memory_styles(self):
  from canvas import ball_fill_level,glow_image
  self.assertAlmostEqual(ball_fill_level(50),0,places=5);self.assertGreater(ball_fill_level(0),.999);self.assertLess(ball_fill_level(100),-.999)
  w=self.window;w.doc=document('纯背景');w.doc['widgets']=[widget('memory_bar',28,45),widget('memory_ball',375,22),widget('memory_gauge',650,22)]+[widget(k,28+i*220,245) for i,k in enumerate(['cpu','gpu','cpu_temp','gpu_temp'])]
  for v in w.doc['widgets'][3:]:v['glow']=True
  w.values.update(memory=75,memory_used=24,memory_total=32,cpu=53,gpu=40,cpu_temp=None,gpu_temp=41);w.rebuild();out=Path(__file__).resolve().parents[1]/'artifacts';w.render_frame().save(str(out/'memory-and-glow-020.png'))
  for level in [0,50,100,None]:
   w.values['memory']=level;self.assertFalse(w.render_frame().isNull())
  w.values.update(memory=None,memory_used=None,memory_total=None);self.assertFalse(w.render_frame().isNull());before=w.doc['brightness'];v=w.doc['widgets'][0];w.gesture('down',v['x']+100,v['y']+70);w.gesture('up',v['x']+100,v['y']+70);self.assertEqual(w.doc['brightness'],before)
  start=time.perf_counter()
  for _ in range(20):w.render_frame()
  print('Warm render ms/frame:',round((time.perf_counter()-start)*1000/20,2),'glow cache hits:',glow_image.cache_info().hits)
 def test_animated_water(self):
  w=self.window;w.doc=document('纯背景');w.doc['widgets']=[widget('memory_ball',0,0)];w.values.update(memory=75,memory_used=24,memory_total=32);w.rebuild();w.animation_time=0;a=w.render_frame();w.animation_time=1.2;b=w.render_frame();self.assertNotEqual(bytes(a.copy(30,28,120,120).constBits()),bytes(b.copy(30,28,120,120).constBits()))
  for rect in [(0,0,180,25),(0,156,180,28)]:self.assertEqual(bytes(a.copy(*rect).constBits()),bytes(b.copy(*rect).constBits()))
  for level in [0,100,None]:
   w.values['memory']=level;w.animation_time=0;a=w.render_frame();w.animation_time=2;b=w.render_frame();self.assertEqual(bytes(a.constBits()),bytes(b.constBits()))
  from canvas import water_surface
  import math
  # A full phase period has no reset jump, including the secondary ripple.
  a=water_surface(80,75,0,5,135,1.6,.7);b=water_surface(80,75,2*math.pi/1.6,5,135,1.6,.7)
  for i in range(a.elementCount()):self.assertAlmostEqual(a.elementAt(i).y,b.elementAt(i).y,places=7)
 def test_protocol(self):
  im=QImage(960,360,QImage.Format.Format_RGB888);im.fill(QColor(0,0,0));im.setPixelColor(0,0,QColor(255,0,0));frame=encode_frame(im);self.assertEqual(len(frame),960*360*3+16);self.assertEqual(frame[:8],bytes([255,0,0,0,0,22,131,192]));self.assertNotIn(b'\xff',frame[8:-8]);self.assertEqual(frame[8+(359*3):8+(359*3)+3],b'\0\0\xfe')
  self.assertEqual(touch_point([1,1,0,0,0,255,15]),('contact',(959.0,359.0)));self.assertEqual(touch_point([1,0,0,0,0,0,0]),('up',None));self.assertIsNone(touch_point([1,1]));worker=DeviceWorker();worker.submit(im);worker.submit(im);self.assertEqual(worker.frames.qsize(),1)
if __name__=='__main__':unittest.main()
