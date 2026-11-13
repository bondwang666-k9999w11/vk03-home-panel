from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPen, QBrush, QFont, QPainter, QLinearGradient, QPixmap, QImage, QPainterPath
from PySide6.QtWidgets import QGraphicsScene, QGraphicsItem
from datetime import datetime
import time, math
from model import volume_wave_count, MONITOR_TYPES, MEMORY_TYPES
from functools import lru_cache
from PIL import Image, ImageFilter

@lru_cache(maxsize=128)
def glow_image(value,family,pixels,color,alpha,width,height,align):
    pad=7;image=QImage(math.ceil(width)+pad*2,math.ceil(height)+pad*2,QImage.Format.Format_RGBA8888);image.fill(Qt.GlobalColor.transparent)
    painter=QPainter(image);painter.setRenderHint(QPainter.RenderHint.TextAntialiasing);font=QFont(family);font.setPixelSize(pixels);painter.setFont(font);ink=QColor(color);ink.setAlphaF(alpha);painter.setPen(ink);painter.drawText(QRectF(pad,pad,width,height),align,value);painter.end()
    source=Image.frombytes('RGBA',(image.width(),image.height()),bytes(image.constBits()));blurred=source.filter(ImageFilter.GaussianBlur(2.4));blurred.putalpha(blurred.getchannel('A').point(lambda a:round(a*.65)));raw=blurred.tobytes()
    return QImage(raw,blurred.width,blurred.height,blurred.width*4,QImage.Format.Format_RGBA8888).copy()

def ball_fill_level(percent):
    # Solve for a horizontal fill whose circular area equals the requested ratio.
    goal=max(0,min(100,percent))/100;lo,hi=-1.0,1.0
    for _ in range(22):
        t=(lo+hi)/2;ratio=(math.acos(t)-t*math.sqrt(max(0,1-t*t)))/math.pi
        if ratio>goal:lo=t
        else:hi=t
    return (lo+hi)/2

def water_surface(level,ratio,stamp,amplitude,wavelength,speed,offset):
    fade=math.sin(math.pi*max(0,min(100,ratio))/100)**.7
    phase=(stamp*speed+offset)%(2*math.pi);path=QPainterPath()
    for x in range(27,154,3):
        y=level+amplitude*fade*(math.sin((x-30)*2*math.pi/wavelength+phase)+.2*math.sin((x-30)*4*math.pi/wavelength-phase*2))
        if x==27:path.moveTo(x,y)
        else:path.lineTo(x,y)
    return path

class PanelScene(QGraphicsScene):
    def __init__(self,studio):
        super().__init__(0,0,960,360);self.studio=studio;self.exporting=False;self.frame=None
    def drawBackground(self,p,rect):
        color=QColor(self.studio.doc['background']);p.fillRect(self.sceneRect(),color)
        if self.frame is not None and not self.frame.isNull():
            image=self.frame;target=self.sceneRect();source=QRectF(image.rect());scale=max(960/image.width(),360/image.height()) if self.studio.doc['fit']=='cover' else min(960/image.width(),360/image.height())
            target=QRectF((960-image.width()*scale)/2,(360-image.height()*scale)/2,image.width()*scale,image.height()*scale)
            p.drawImage(target,image,source)
        else:
            g=QLinearGradient(0,360,960,0);g.setColorAt(0,color.darker(140));g.setColorAt(1,color.lighter(170));p.fillRect(self.sceneRect(),g)
    def drawForeground(self,p,rect):
        message=getattr(self.studio,'screen_message',None)
        if message and time.monotonic()<message[1]:
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(12,25,28,235));p.drawRoundedRect(QRectF(290,294,380,48),12,12);p.setPen(QColor('#f3fff8'));f=QFont('Microsoft YaHei');f.setPixelSize(22);p.setFont(f);p.drawText(QRectF(290,294,380,48),Qt.AlignmentFlag.AlignCenter,message[0])
        alpha=1-self.studio.doc['brightness']/100
        if alpha:p.fillRect(self.sceneRect(),QColor(0,0,0,round(alpha*255)))

class WidgetItem(QGraphicsItem):
    def __init__(self,v,studio):
        super().__init__();self.v=v;self.studio=studio;self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable|QGraphicsItem.GraphicsItemFlag.ItemIsMovable|QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges);self.setPos(v['x'],v['y']);self.setCursor(Qt.CursorShape.SizeAllCursor)
    def boundingRect(self):return QRectF(0,0,self.v['w'],self.v['h'])
    def itemChange(self,change,value):
        if change==QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            return QPointF(max(0,min(960-self.v['w'],value.x())),max(0,min(360-self.v['h'],value.y())))
        return super().itemChange(change,value)
    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        if self.v['x']!=self.pos().x() or self.v['y']!=self.pos().y():
            self.v['x']=round(self.pos().x());self.v['y']=round(self.pos().y());self.studio.commit()
    def paint(self,p,option,widget=None):
        v=self.v;w,h=v['w'],v['h'];kind=v['type'];p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # All internal coordinates scale with the component footprint.
        p.save();base={'music':(270,128),'volume':(270,64),'brightness':(270,64),'clock':(220,86),'cpu':(170,80),'memory':(170,80),'text':(180,64),'gpu':(170,80),'cpu_temp':(170,80),'gpu_temp':(170,80),'memory_bar':(280,94),'memory_ball':(180,186),'memory_gauge':(220,186)}.get(kind,(104,104));p.scale(w/base[0],h/base[1]);bw,bh=base
        if not v['transparent']:
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(10,27,25,round(v['opacity']*255)));p.drawRoundedRect(QRectF(0,0,bw,bh),16,16)
        color=QColor(v['color']);color.setAlphaF(v['text_alpha']);font=QFont(v['font'],v['size']);font.setPixelSize(v['size'])
        def text(x,y,width,height,value,size=None,align=Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter):
            if not v['show_text']:return
            p.save();f=QFont(font);f.setPixelSize(round(size*v['size']/20) if size else v['size']);p.setFont(f);p.setPen(color)
            if kind in MONITOR_TYPES and v.get('glow',False) and v['text_alpha']>0:
                halo=glow_image(str(value),v['font'],f.pixelSize(),v['color'],v['text_alpha'],width,height,align);p.drawImage(QPointF(x-7,y-7),halo)
            p.drawText(QRectF(x,y,width,height),align,str(value));p.restore()
        def line(x1,y1,x2,y2,width=3):p.setPen(QPen(QColor(v['color']),width,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap));p.drawLine(QPointF(x1,y1),QPointF(x2,y2))
        if kind in ('shortcut','shutdown','restart'):
            image=self.studio.images.get(v['icon'])
            if image and not image.isNull():
                p.save()
                path=QPainterPath();path.addRoundedRect(QRectF(0,0,bw,bh),16,16);p.setClipPath(path);p.setOpacity(v['icon_alpha']);side=min(image.width(),image.height());p.drawPixmap(QRectF(0,0,bw,bh),image,QRectF((image.width()-side)/2,(image.height()-side)/2,side,side));p.restore()
            elif kind=='shortcut':
                p.setPen(QPen(QColor(v['color']),2.5));p.setBrush(Qt.BrushStyle.NoBrush)
                for x,y in [(33,24),(55,24),(33,46),(55,46)]:p.drawRoundedRect(QRectF(x,y,16,16),4,4)
            else:
                p.setPen(QPen(QColor('#ffaaa6' if kind=='shutdown' else '#8ce5c3'),3.5,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap));p.setBrush(Qt.BrushStyle.NoBrush);p.drawArc(QRectF(30,20,44,44),40*16,280*16)
                if kind=='shutdown':line(52,17,52,39,3.5)
                else:line(72,17,73,32);line(73,32,59,32)
            text(4,72,bw-8,26,v['name'],align=Qt.AlignmentFlag.AlignCenter)
        elif kind=='music':
            text(16,8,235,22,'正在播放',12);title=self.studio.values.get('media',{}).get('title') or '暂无播放内容';metrics=p.fontMetrics();text(16,34,238,34,metrics.elidedText(title,Qt.TextElideMode.ElideRight,225))
            for i in range(4):
                x=17+i*59;p.setBrush(QColor(255,255,255,20));p.setPen(Qt.PenStyle.NoPen);p.drawRoundedRect(QRectF(x,83,48,31),8,8)
                if i==0:line(x+13,92,x+13,105);line(x+29,92,x+18,99);line(x+18,99,x+29,105)
                elif i==1:line(x+18,91,x+30,99);line(x+30,99,x+18,106);line(x+18,91,x+18,106)
                elif i==2:line(x+19,92,x+19,105,4);line(x+28,92,x+28,105,4)
                else:line(x+34,92,x+34,105);line(x+18,92,x+29,99);line(x+29,99,x+18,105)
        elif kind in ('volume','brightness'):
            value=self.studio.values.get('volume',0) if kind=='volume' else self.studio.doc['brightness'];value=value if isinstance(value,(int,float)) else 0
            text(6,0,190,25,v['name'],16)
            if self.studio.touch_active and self.studio.touch_active['id']==v['id']:text(175,0,45,25,str(round(value)),16,Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
            if kind=='volume':
                line(236,10,241,10,2);line(241,10,246,5,2);line(246,5,246,20,2);line(246,20,241,15,2);line(241,15,236,15,2);line(236,10,236,15,2)
                waves=volume_wave_count(value,self.studio.values.get('muted',False))
                if not waves:line(252,10,257,15,1.6);line(257,10,252,15,1.6)
                else:
                    p.setPen(QPen(QColor(v['color']),1.8,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap));p.setBrush(Qt.BrushStyle.NoBrush)
                    for r in (4,8,12)[:waves]:p.drawArc(QRectF(248-r,12.5-r,r*2,r*2),-50*16,100*16)
            else:
                p.setPen(QPen(QColor(v['color']),1.7));p.setBrush(Qt.BrushStyle.NoBrush);p.drawEllipse(QRectF(242,6,12,12))
                for angle in range(0,360,45):
                    a=math.radians(angle);p.drawLine(QPointF(248+9*math.cos(a),12+9*math.sin(a)),QPointF(248+13*math.cos(a),12+13*math.sin(a)))
            p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(QColor('#d7d2f4'),1.5));p.drawRoundedRect(QRectF(7,37,253,14),7,7)
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(v.get('fill_color','#a397ec')));p.drawRoundedRect(QRectF(8,38,251*value/100,12),6,6)
        elif kind in MEMORY_TYPES:
            stats=self.studio.values;raw=stats.get('memory');valid=isinstance(raw,(int,float)) and math.isfinite(raw);ratio=max(0,min(100,raw)) if valid else 0
            used,total=stats.get('memory_used'),stats.get('memory_total');known=all(isinstance(n,(int,float)) and math.isfinite(n) and n>=0 for n in (used,total)) and total>0
            caption=f'{used:.1f} / {total:.1f} GB' if known else '— / — GB';percent=f'{ratio:.0f}%' if valid else '—';accent=QColor(v.get('fill_color','#78dfb0'));center=Qt.AlignmentFlag.AlignCenter
            if kind=='memory_bar':
                text(4,0,195,25,v['name'],15);text(200,0,76,25,percent,21,Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
                p.setBrush(QColor(255,255,255,20));p.setPen(QPen(QColor(210,230,225,100),1));p.drawRoundedRect(QRectF(4,35,272,14),7,7)
                p.setPen(Qt.PenStyle.NoPen);p.setBrush(accent);p.drawRoundedRect(QRectF(5,36,270*ratio/100,12),6,6)
                text(4,59,272,24,(f'已用 {used:.1f} GB  /  总量 {total:.1f} GB' if known else '已用 — GB  /  总量 — GB'),13)
            elif kind=='memory_ball':
                text(0,0,180,23,v['name'],14,center);circle=QRectF(30,28,120,120);path=QPainterPath();path.addEllipse(circle);p.save();p.setClipPath(path);p.fillRect(circle,QColor(255,255,255,22));level=88+60*ball_fill_level(ratio)
                gradient=QLinearGradient(0,28,0,148);gradient.setColorAt(0,accent.lighter(125));gradient.setColorAt(1,accent.darker(140))
                if ratio>=100:p.fillRect(circle,gradient)
                elif ratio>0:
                    stamp=getattr(self.studio,'animation_time',0)
                    for amplitude,wavelength,speed,offset,alpha,shift in [(5.0,135,1.6,.7,.28,-1.8),(4.0,108,-1.2,2.3,.40,0),(3.3,122,.8,4.1,.88,1.3)]:
                        surface=water_surface(level+shift*math.sin(math.pi*ratio/100),ratio,stamp,amplitude,wavelength,speed,offset);water=QPainterPath(surface);water.lineTo(153,151);water.lineTo(27,151);water.closeSubpath();p.save();p.setOpacity(alpha);p.fillPath(water,gradient);rim=QColor(accent.lighter(155));rim.setAlpha(110);p.setPen(QPen(rim,.9));p.drawPath(surface);p.restore()
                p.restore();p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(QColor(220,250,238,140),1.5));p.drawEllipse(circle);text(30,69,120,35,percent,29,center);text(0,157,180,25,caption,14,center)
            else:
                text(0,0,220,23,v['name'],14,center);dial=QRectF(42,46,136,136);p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(QColor(255,255,255,32),9,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap));p.drawArc(dial,225*16,-270*16)
                if ratio>0:p.setPen(QPen(accent,9,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap));p.drawArc(dial,225*16,round(-270*ratio/100*16))
                for i in range(11):
                    a=math.radians(225-27*i);r1=54 if i%5==0 else 57;r2=62;p.setPen(QPen(QColor(220,244,235,160),1.2));p.drawLine(QPointF(110+r1*math.cos(a),114-r1*math.sin(a)),QPointF(110+r2*math.cos(a),114-r2*math.sin(a)))
                if valid:
                    a=math.radians(225-2.7*ratio);p.setPen(QPen(QColor(v['color']),2.5,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap));p.drawLine(QPointF(110-9*math.cos(a),114+9*math.sin(a)),QPointF(110+49*math.cos(a),114-49*math.sin(a)));p.setBrush(accent);p.setPen(Qt.PenStyle.NoPen);p.drawEllipse(QPointF(110,114),5,5)
                text(68,136,84,25,percent,23,center);text(0,164,220,22,caption,14,center)

        elif kind=='clock':
            now=datetime.now();text(0,0,bw,52,now.strftime('%H:%M:%S'),34,Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter);text(0,54,bw,24,now.strftime('%Y.%m.%d')+'  '+['周一','周二','周三','周四','周五','周六','周日'][now.weekday()],15,Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        elif kind in ('cpu','memory','gpu','cpu_temp','gpu_temp'):
            value=self.studio.values.get(kind);text(0,0,bw,24,v['name'],15);text(0,26,bw,45,'—' if value is None else f'{value:.0f}'+('°C' if kind.endswith('_temp') else '%'),32)
        else:text(4,0,bw-8,bh,v['name'])
        p.restore()
        if self.isSelected() and not self.scene().exporting:
            p.setPen(QPen(QColor('#77e5b9'),1.5,Qt.PenStyle.DashLine));p.setBrush(Qt.BrushStyle.NoBrush);p.drawRoundedRect(self.boundingRect().adjusted(1,1,-1,-1),12,12)
