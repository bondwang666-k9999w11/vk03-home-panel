import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication,QTimer
from system_bridge import SystemBridge
a=QCoreApplication([]);bridge=SystemBridge(Path(__file__).resolve().parents[1]);done=[]
def receive(v):
 done.append(v);a.quit()
bridge.snapshot.connect(receive);bridge.post('state.get');QTimer.singleShot(12000,a.quit);a.exec();bridge.close()
assert done, 'No system snapshot received'
assert isinstance(done[0].get('volume'),(int,float)), 'Volume not available'
print('PASS native Windows read-only snapshot; no actions or USB calls')
