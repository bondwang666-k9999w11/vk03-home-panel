"""MS912C USB transport, based on the existing user-authored VK03 protocol.
Import is passive. Only an explicit DeviceWorker.start() opens hardware.
"""
import struct, time, queue, threading, os
from pathlib import Path
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage, QTransform


def encode_frame(image):
    if image.width()!=960 or image.height()!=360:raise ValueError('Expected 960x360')
    physical=image.transformed(QTransform().rotate(90)).convertToFormat(QImage.Format.Format_BGR888)
    body=bytes(physical.constBits())
    if len(body)!=360*960*3:raise ValueError('Unexpected image stride')
    header=bytearray(struct.pack('<I',255)+b'\0\0\0\0');header[5]=360>>4;header[6]=((360&15)<<4)|(960>>8);header[7]=960&255
    return bytes(header)+body.replace(b'\xff',b'\xfe')+bytes([255,192,0,0,0,0,0,0])


def touch_point(data):
    if len(data)<7: return None
    if data[1]==0:return ('up',None)
    x=data[3]|data[4]<<8;y=data[5]|data[6]<<8
    if x>4095 or y>4095:return None
    return ('contact',(y*959/4095,(4095-x)*359/4095))

class DeviceWorker(QThread):
    status=Signal(str);gesture=Signal(str,float,float);failure=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent);self.frames=queue.Queue(1);self.stop_flag=threading.Event();self.control=None;self.touch=None;self.usb=None;self.interface=None;self.reader=None;self.count=0
    def submit(self,image):
        try:self.frames.get_nowait()
        except queue.Empty:pass
        try:self.frames.put_nowait(image.copy())
        except queue.Full:pass
    def stop(self): self.stop_flag.set()
    def feature(self,data):
        if self.control.send_feature_report(b'\0'+bytes(data[:8]).ljust(8,b'\0'))<=0:raise RuntimeError('HID命令发送失败')
    def read(self,address):
        self.feature([181,address>>8,address&255]);r=self.control.get_feature_report(0,9)
        if len(r)<9:raise RuntimeError('HID状态读取不完整')
        return r[4]
    def write(self,address,value):self.feature([182,address>>8,address&255,value&255])
    def command(self,data,register,pause=.02):
        self.feature(data);time.sleep(pause);end=time.monotonic()+2
        while time.monotonic()<end:
            if self.stop_flag.is_set():raise RuntimeError('连接已取消')
            if self.read(register)==0:return
            time.sleep(.005)
        raise RuntimeError('屏幕初始化等待超时')
    def initialize(self):
        self.command([166,3,3],0xc558,.01);self.write(0xdeee,1);self.command([166,7,1],0xc454,.1);self.command([166,5,0],0xc555,.01)
        self.write(0xf005,self.read(0xf005)&~16);self.command([166,4,0],0xc555);time.sleep(.05)
        self.command([166,1,1,104,3,192,17,0],0xc555);self.command([166,2,160,0,1,104,3,192],0xc557);self.command([166,4,1],0xc555)
    def send(self,image,fid):
        frame=encode_frame(image);offset=0
        while offset<len(frame):
            if self.stop_flag.is_set():return
            n=self.usb.write(4,frame[offset:offset+0x80000],timeout=1500)
            if n<=0:raise RuntimeError('USB传输中断')
            offset+=n
        self.usb.write(4,b'',timeout=1500);self.feature([166,0,fid,100,0,0,0,0]);self.count+=1
    def read_touch(self):
        down=False;last=(0,0)
        try:
            while not self.stop_flag.is_set():
                packet=self.touch.read(64,20)
                if not packet:continue
                parsed=touch_point(packet)
                if not parsed:continue
                phase,point=parsed
                if phase=='up':
                    if down:self.gesture.emit('up',*last);down=False
                else:
                    last=point;self.gesture.emit('move' if down else 'down',*point);down=True
        except Exception as e:
            if not self.stop_flag.is_set():self.failure.emit('触摸连接中断：'+str(e));self.stop_flag.set()
        finally:
            if down:self.gesture.emit('cancel',*last)
    def run(self):
        import hid, usb.core, usb.util, usb.backend.libusb0
        try:
            self.status.emit('正在连接设备…')
            backend=usb.backend.libusb0.get_backend(find_library=lambda _:str(Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/libusb0.dll'))
            if backend is None:raise RuntimeError('缺少64位 libusb0 驱动库。请先安装兼容的VK03驱动；预览不需要驱动。')
            self.usb=usb.core.find(idVendor=0x345f,idProduct=0x9132,backend=backend)
            if self.usb is None:raise RuntimeError('未找到VK03显示设备 345F:9132')
            config=self.usb.get_active_configuration();interfaces=[i for i in config if any(e.bEndpointAddress==4 and e.bmAttributes&3==2 for e in i)]
            if not interfaces:raise RuntimeError('找不到USB显示接口')
            self.interface=interfaces[0].bInterfaceNumber;usb.util.claim_interface(self.usb,self.interface)
            devices=hid.enumerate(0x345f,0x9132)
            if not devices:raise RuntimeError('未找到屏幕HID控制接口')
            self.control=hid.device();self.control.open_path(devices[0]['path'])
            if [self.read(0xf000+i) for i in range(3)]!=[183,22,10] or self.read(49)!=6:raise RuntimeError('不是已验证的360×960 MS912C设备')
            touches=hid.enumerate(0x374a,0xa401)
            if not touches:raise RuntimeError('未找到VK03触摸接口')
            self.touch=hid.device();self.touch.open_path(touches[0]['path'])
            first=self.frames.get(timeout=3);self.initialize();self.send(first,1);self.write(0xf005,self.read(0xf005)|16);self.command([166,5,1],0xc555,.01)
            self.reader=threading.Thread(target=self.read_touch,daemon=True);self.reader.start();self.status.emit('已连接 · 960 × 360');fid=0
            while not self.stop_flag.is_set():
                try:image=self.frames.get(timeout=.5)
                except queue.Empty:continue
                self.send(image,fid);fid^=1
        except Exception as e:
            if not self.stop_flag.is_set():self.failure.emit(str(e))
        finally:
            self.stop_flag.set()
            if self.reader:self.reader.join(timeout=1)
            if self.touch:self.touch.close()
            if self.control:self.control.close()
            if self.usb:
                try:usb.util.dispose_resources(self.usb)
                except Exception:pass
            self.status.emit('未连接')
