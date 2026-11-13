import os,sys,time
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer,QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer,QVideoSink
app=QApplication([]);player=QMediaPlayer();sink=QVideoSink();player.setVideoSink(sink);colors=[];errors=[]
def frame(v):
 if v.isValid():
  im=v.toImage();colors.append(im.pixelColor(im.width()//2,im.height()//2).name())
sink.videoFrameChanged.connect(frame);player.errorOccurred.connect(lambda *args:errors.append(player.errorString()));player.setSource(QUrl.fromLocalFile(str(Path(__file__).parent/'fixtures/two-colors.avi')));player.play();QTimer.singleShot(3200,app.quit);app.exec();player.stop();assert len(set(colors))>=2,(colors,errors);print('PASS video decoding: multiple frames and both colors, no audio or USB')
