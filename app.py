"""VK03 Studio: independent desktop editor and direct USB output."""
import sys,os,copy,uuid,time,shutil,logging
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QRectF,QUrl,QStandardPaths,QLockFile
from PySide6.QtGui import QImage,QPainter,QPixmap,QColor,QFont,QIcon,QImageReader,QAction,QFontDatabase
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QHBoxLayout,QVBoxLayout,QLabel,QPushButton,QStackedWidget,QGraphicsView,QFormLayout,QSpinBox,QSlider,QLineEdit,QCheckBox,QComboBox,QFontComboBox,QFileDialog,QColorDialog,QMessageBox,QListWidget,QScrollArea,QSplitter,QFrame,QSystemTrayIcon,QMenu,QSizePolicy,QLayout
from PySide6.QtMultimedia import QMediaPlayer,QVideoSink
from model import TYPES,widget,document,validate,save,load,copy_style,copy_monitor_style,MONITOR_TYPES,MEMORY_TYPES
from canvas import PanelScene,WidgetItem
from device import DeviceWorker
from system_bridge import SystemBridge
from projects import export_bundle,import_bundle
ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
STYLE='''QWidget{background:#151b22;color:#dfe8ef;font-family:"Microsoft YaHei";font-size:13px} QLabel{background:transparent} QLabel#brand{font-size:22px;font-weight:700;color:#f3fff9} QLabel#heading{font-size:25px;font-weight:600} QLabel#muted{color:#93a3b4;font-size:12px} QFrame#card{background:#1c2530;border:1px solid #303d4b;border-radius:12px} QPushButton{background:#263342;border:1px solid #364657;border-radius:7px;padding:8px 13px} QPushButton:hover{background:#35485b} QPushButton:checked{background:#25483e;color:#9af0ca;border-color:#538a71} QPushButton#primary{background:#8ce4bb;color:#11271e;font-weight:600;border:0} QLineEdit,QSpinBox,QComboBox,QFontComboBox{background:#111922;border:1px solid #394959;border-radius:5px;padding:6px;min-height:20px} QScrollArea{border:0} QScrollBar:vertical{background:#151b22;width:9px} QScrollBar::handle:vertical{background:#425162;border-radius:4px;min-height:28px} QListWidget{border:0;background:#19222c;outline:none} QListWidget::item{padding:11px;border-bottom:1px solid #263441} QListWidget::item:selected{background:#2a4a41;color:#a9f5d0} QGraphicsView{border:0;background:#0c1218;border-radius:12px} QSlider::groove:horizontal{height:5px;background:#354454;border-radius:2px} QSlider::handle:horizontal{background:#a397ec;width:13px;margin:-5px 0;border-radius:6px} QCheckBox{spacing:9px;background:transparent}'''
def button(text,callback=None,primary=False):
    b=QPushButton(text)
    if callback:b.clicked.connect(callback)
    if primary:b.setObjectName('primary')
    return b

def label(text,muted=False):
    l=QLabel(text);l.setWordWrap(True)
    if muted:l.setObjectName('muted')
    return l

class FitView(QGraphicsView):
    def fit(self):self.fitInView(self.scene().sceneRect().adjusted(-24,-24,24,24),Qt.AspectRatioMode.KeepAspectRatio)
    def resizeEvent(self,e):super().resizeEvent(e);self.fit()
    def showEvent(self,e):super().showEvent(e);self.fit()

class Studio(QMainWindow):
    def __init__(self,data_dir=None,start_bridge=True):
        super().__init__()
        for fontname in ('msyh.ttc','segoeui.ttf'):
            fontpath=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'Fonts'/fontname
            if fontpath.is_file():QFontDatabase.addApplicationFont(str(fontpath))
        self.setWindowTitle('VK03 Studio · 独立控制面板');self.resize(1440,880);self.setMinimumSize(1120,720)
        self.data=Path(data_dir or QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation));self.data.mkdir(parents=True,exist_ok=True);self.config=self.data/'scene.json';self.doc=document();self.load_error=''
        if self.config.exists():
            try:self.doc=load(self.config)
            except Exception as e:self.load_error=str(e)
        self.values={'volume':0,'muted':False,'media':{},'cpu':None,'memory':None};self.images={};self.device=None;self.bridge=None;self.rebuilding=False;self.touch_active=None;self.power_armed=None;self.last_volume=0;self.volume_hold=0;self.volume_pending=None;self.history=[copy.deepcopy(self.doc)];self.future=[];self.quitting=False;self.manual_disconnect=True
        self.animation_time=time.monotonic();self.movie=None;self.player=QMediaPlayer(self);self.sink=QVideoSink(self);self.player.setVideoSink(self.sink);self.player.setLoops(QMediaPlayer.Loops.Infinite);self.sink.videoFrameChanged.connect(self.video_frame);self.player.errorOccurred.connect(lambda *_:self.message('视频无法播放：'+self.player.errorString()))
        self.build_ui();self.rebuild();self.load_media();self.build_tray();self.autosave=QTimer(self);self.autosave.setSingleShot(True);self.autosave.timeout.connect(self.save_doc)
        self.frame_timer=QTimer(self);self.frame_timer.timeout.connect(self.tick);self.frame_timer.start(round(1000/self.doc['fps']));self.poll=QTimer(self);self.poll.timeout.connect(self.refresh_state);self.poll.start(1000)
        if start_bridge:self.bridge=SystemBridge(ROOT);self.bridge.snapshot.connect(self.receive_state);self.bridge.error.connect(self.message);self.bridge.post('state.get')
        import psutil
        psutil.cpu_percent()
        if self.load_error:self.message('原配置无法载入，暂以默认方案打开；原文件未覆盖：'+self.load_error)
        for key,fn in [('Ctrl+S',self.save_doc),('Ctrl+Z',self.undo),('Ctrl+Y',self.redo)]:
            a=QAction(self);a.setShortcut(key);a.triggered.connect(fn);self.addAction(a)
    def build_ui(self):
        root=QWidget();outer=QVBoxLayout(root);outer.setContentsMargins(18,14,18,14);outer.setSpacing(14);self.setCentralWidget(root);top=QHBoxLayout();brand=label('VK03 STUDIO');brand.setObjectName('brand');top.addWidget(brand);top.addWidget(label('独立版 / 0.2.1 预览',True));top.addStretch();self.device_badge=label('●  设备未连接',True);top.addWidget(self.device_badge);self.connect_button=button('连接屏幕',self.connect_device,True);top.addWidget(self.connect_button);outer.addLayout(top)
        body=QHBoxLayout();outer.addLayout(body,1);nav=QVBoxLayout();nav.setSpacing(10);self.pages=QStackedWidget();self.nav_buttons=[]
        for index,name in enumerate(['屏幕编辑','方案库','设备','设置 / 关于']):
            b=button(name,lambda _,i=index:self.show_page(i));b.setCheckable(True);b.setFixedWidth(108);nav.addWidget(b);self.nav_buttons.append(b)
        nav.addStretch();nav.addWidget(label('960 × 360\n横向触摸屏',True));body.addLayout(nav);body.addWidget(self.pages,1);self.build_editor();self.build_schemes();self.build_device();self.build_about();self.show_page(0);self.notice=label('编辑预览不会执行系统控制；连接后由小屏触摸执行。',True);outer.addWidget(self.notice)
    def show_page(self,i):
        self.pages.setCurrentIndex(i)
        for n,b in enumerate(self.nav_buttons):b.setChecked(n==i)
    def build_editor(self):
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(12,0,0,0);row=QHBoxLayout();heading=label('屏幕编辑');heading.setObjectName('heading');row.addWidget(heading);row.addStretch();row.addWidget(button('撤销',self.undo));row.addWidget(button('重做',self.redo));row.addWidget(button('保存方案',self.save_doc,True));layout.addLayout(row);split=QSplitter(Qt.Orientation.Horizontal);layout.addWidget(split,1)
        left=QWidget();left.setMinimumWidth(180);ll=QVBoxLayout(left);ll.setContentsMargins(0,8,8,0);ll.addWidget(label('组件与图层'));self.kind_select=QComboBox()
        for key,(name,*_) in TYPES.items():self.kind_select.addItem(name,key)
        ll.addWidget(self.kind_select);ll.addWidget(button('＋ 添加组件',self.add_widget));self.layers=QListWidget();self.layers.currentRowChanged.connect(self.layer_selected);ll.addWidget(self.layers,1)
        r=QHBoxLayout();r.addWidget(button('复制',self.duplicate));r.addWidget(button('删除',self.remove_widget));ll.addLayout(r);r=QHBoxLayout();r.addWidget(button('上移',lambda:self.reorder(-1)));r.addWidget(button('下移',lambda:self.reorder(1)));ll.addLayout(r);split.addWidget(left)
        center=QWidget();cl=QVBoxLayout(center);cl.setContentsMargins(8,8,8,0);self.scene=PanelScene(self);self.scene.selectionChanged.connect(self.scene_selected);self.view=FitView(self.scene);self.view.setRenderHints(QPainter.RenderHint.Antialiasing|QPainter.RenderHint.SmoothPixmapTransform);cl.addWidget(self.view,1);cl.addWidget(label('拖动调整位置 · 右侧编辑尺寸 · 小屏使用同一份画面',True));bg=QFrame();bg.setObjectName('card');bl=QVBoxLayout(bg);row=QHBoxLayout();row.addWidget(label('背景'));row.addStretch();row.addWidget(button('图片 / GIF / 视频',self.choose_background));row.addWidget(button('清除',self.clear_background));bl.addLayout(row)
        row=QHBoxLayout();row.addWidget(button('底色',self.choose_bg_color));self.fit=QComboBox();self.fit.addItem('填满屏幕（裁剪）','cover');self.fit.addItem('完整显示（留白）','contain');self.fit.currentIndexChanged.connect(self.change_fit);row.addWidget(self.fit,1);self.fps=QComboBox();self.fps.addItem('15 FPS',15);self.fps.addItem('30 FPS',30);self.fps.currentIndexChanged.connect(self.change_fps);row.addWidget(self.fps);bl.addLayout(row);self.pure=QCheckBox('仅播放背景 · 保留组件配置');self.pure.toggled.connect(self.change_pure);bl.addWidget(self.pure);self.media_label=label('渐变纯色背景',True);bl.addWidget(self.media_label);cl.addWidget(bg);split.addWidget(center)
        scroll=QScrollArea();self.property_scroll=scroll;scroll.setWidgetResizable(True);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);scroll.setMinimumWidth(280);scroll.setMaximumWidth(360);self.props=QWidget();self.props.setMinimumWidth(0);self.props.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred);self.form=QFormLayout(self.props);self.form.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint);self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow);self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows);self.form.setContentsMargins(12,8,4,8);self.form.setVerticalSpacing(12);self.form.addRow(label('组件属性'));self.selection_name=label('选择一个组件');self.form.addRow(self.selection_name);self.fields={}
        for key,title,low,high in [('x','X',0,959),('y','Y',0,359),('w','宽度',40,960),('h','高度',32,360),('size','字号',10,80)]:
            box=QSpinBox();box.setRange(low,high);box.editingFinished.connect(self.apply_properties);self.fields[key]=box;self.form.addRow(title,box)
        self.name_field=QLineEdit();self.name_field.editingFinished.connect(self.apply_properties);self.form.addRow('显示文字',self.name_field);self.font_field=QFontComboBox();self.font_field.currentFontChanged.connect(lambda *_:self.apply_properties());self.form.addRow('字体',self.font_field);self.color_button=button('选择颜色',self.choose_text_color);self.form.addRow('文字颜色',self.color_button);self.fill_color_button=button('选择填充颜色',self.choose_fill_color);self.form.addRow('填充颜色',self.fill_color_button)
        for key,title in [('text_alpha','文字透明度'),('opacity','底板透明度'),('icon_alpha','图片透明度')]:
            box=QSlider(Qt.Orientation.Horizontal);box.setRange(0,100);box.sliderReleased.connect(self.apply_properties);self.fields[key]=box;self.form.addRow(title,box)
        self.show_text=QCheckBox('显示文字');self.show_text.toggled.connect(self.apply_properties);self.form.addRow(self.show_text);self.glow=QCheckBox('文字光晕');self.glow.toggled.connect(self.apply_properties);self.form.addRow(self.glow);self.transparent=QCheckBox('无边框 / 透明底');self.transparent.toggled.connect(self.apply_properties);self.form.addRow(self.transparent);self.target=QLineEdit();self.target.setPlaceholderText('程序、文件夹或网址');self.target.editingFinished.connect(self.apply_properties);self.form.addRow('快捷目标',self.target)
        for name,fn in [('选择程序 / 快捷方式',self.choose_target),('选择文件夹',self.choose_folder),('设置图片图标',self.choose_icon),('移除图片图标',self.clear_icon),('样式套用到同类组件',self.reuse_style)]:self.form.addRow(button(name,fn))
        for child in self.props.findChildren(QWidget):
            if isinstance(child,(QPushButton,QLineEdit,QComboBox,QSpinBox)):
                child.setMinimumWidth(0);child.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
                if isinstance(child,QComboBox):child.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);child.setMinimumContentsLength(5)
        scroll.setWidget(self.props);split.addWidget(scroll);split.setSizes([190,730,275]);self.pages.addWidget(page)
    def build_schemes(self):
        page=QWidget();l=QVBoxLayout(page);title=label('方案库');title.setObjectName('heading');l.addWidget(title);l.addWidget(label('从一个布局开始，把屏幕留给你喜欢的内容。',True))
        for title,detail in [('日常控制','媒体、音量、亮度、六个快捷按钮和时钟'),('轻量监控','CPU、内存与日期时间，中间留白欣赏背景'),('纯背景','只播放图片或视频，之后也能自由添加组件')]:
            card=QFrame();card.setObjectName('card');row=QHBoxLayout(card);row.addWidget(label(title+'\n'+detail));row.addStretch();row.addWidget(button('使用此布局',lambda _,t=title:self.use_template(t)));l.addWidget(card)
        row=QHBoxLayout();row.addWidget(button('导入 .vk03 方案',self.import_scene));row.addWidget(button('导出方案（包含素材）',self.export_scene));row.addStretch();l.addLayout(row);l.addStretch();self.pages.addWidget(page)
    def build_device(self):
        page=QWidget();l=QVBoxLayout(page);title=label('设备');title.setObjectName('heading');l.addWidget(title);l.addWidget(label('VK03 · 960 × 360 横向显示'));l.addWidget(label('独立 USB 通信，不启动 MythTool。连接前请退出其他屏幕控制程序。',True));self.device_detail=label('尚未连接。编辑与保存方案无需连接设备。');l.addWidget(self.device_detail);l.addWidget(button('连接 / 断开屏幕',self.connect_device));self.auto_reconnect=QCheckBox('连接中断后自动重连');self.auto_reconnect.setChecked(True);l.addWidget(self.auto_reconnect);l.addWidget(label('小屏画面亮度'));self.brightness=QSlider(Qt.Orientation.Horizontal);self.brightness.setRange(10,100);self.brightness.sliderReleased.connect(self.change_brightness);l.addWidget(self.brightness);l.addWidget(label('10–100% · 软件调暗，不改变屏幕背光',True));self.stats=label('输出：未连接',True);l.addWidget(self.stats);l.addStretch();self.pages.addWidget(page)
    def build_about(self):
        page=QWidget();l=QVBoxLayout(page);title=label('VK03 Studio');title.setObjectName('heading');l.addWidget(title);l.addWidget(label('独立控制面板 0.2.1 · 实机验收预览版'));l.addWidget(label('原创编辑器、渲染器和直接 USB 输出。\n不加载 MythCool.exe、原厂 .node 或 JSC。\n关机/重启需在小屏2.5秒内点按同一按钮两次。\nCPU / 内存占用直接读取；NVIDIA GPU 可通过 nvidia-smi 读取。CPU 温度需已有 LibreHardwareMonitor WMI 服务，缺失时显示 —。\n关闭窗口后保留托盘运行，右键托盘退出。\n使用已有兼容USB驱动，不自动更换系统驱动。',True));l.addWidget(button('打开配置文件夹',lambda:os.startfile(str(self.data))));l.addStretch();self.pages.addWidget(page)
    def build_tray(self):
        pix=QPixmap(64,64);pix.fill(QColor('#162c26'));p=QPainter(pix);p.setPen(QColor('#98edc5'));p.setFont(QFont('Segoe UI',30));p.drawText(pix.rect(),Qt.AlignmentFlag.AlignCenter,'S');p.end();icon=QIcon(pix);self.setWindowIcon(icon);self.tray=QSystemTrayIcon(icon,self);menu=QMenu();menu.addAction('打开 VK03 Studio',self.showNormal);menu.addAction('保存方案',self.save_doc);menu.addSeparator();menu.addAction('退出',self.quit_app);self.tray.setContextMenu(menu);self.tray.setToolTip('VK03 Studio');self.tray.activated.connect(lambda reason:self.showNormal() if reason==QSystemTrayIcon.ActivationReason.DoubleClick else None);self.tray.show()
    def message(self,text):
        if hasattr(self,'notice'):self.notice.setText(str(text))
        logging.info(str(text))
    def selected(self):
        items=self.scene.selectedItems();return items[0].v if items else None
    def rebuild(self,selected=None):
        self.rebuilding=True;self.scene.clear();self.layers.clear();self.images={}
        for i,v in enumerate(self.doc['widgets']):
            if v['icon']:
                image=QPixmap(v['icon'])
                if not image.isNull():self.images[v['icon']]=image
            item=WidgetItem(v,self);item.setZValue(i);item.setVisible(not self.doc['background_only']);self.scene.addItem(item);self.layers.addItem(v['name']+'  ·  '+TYPES[v['type']][0])
            if v['id']==selected:item.setSelected(True);self.layers.setCurrentRow(i)
        self.fit.blockSignals(True);self.fit.setCurrentIndex(0 if self.doc['fit']=='cover' else 1);self.fit.blockSignals(False);self.fps.blockSignals(True);self.fps.setCurrentIndex(0 if self.doc['fps']==15 else 1);self.fps.blockSignals(False);self.pure.blockSignals(True);self.pure.setChecked(self.doc['background_only']);self.pure.blockSignals(False);self.brightness.setValue(self.doc['brightness']);self.rebuilding=False;self.show_properties();self.scene.update()
    def scene_selected(self):
        if self.rebuilding or self.quitting:return
        v=self.selected();self.layers.blockSignals(True);self.layers.setCurrentRow(next((i for i,w in enumerate(self.doc['widgets']) if v and w['id']==v['id']),-1));self.layers.blockSignals(False);self.show_properties()
    def layer_selected(self,index):
        if self.rebuilding:return
        self.scene.blockSignals(True);self.scene.clearSelection()
        if 0<=index<len(self.doc['widgets']):
            wanted=self.doc['widgets'][index]['id']
            for item in self.scene.items():
                if item.v['id']==wanted:item.setSelected(True)
        self.scene.blockSignals(False);self.show_properties()
    def show_properties(self):
        self.rebuilding=True;v=self.selected();self.props.setEnabled(bool(v));self.selection_name.setText(v['name'] if v else '选择一个组件')
        if v:
            for key,box in self.fields.items():box.setValue(round((1-v[key])*100) if key.endswith('alpha') or key=='opacity' else round(v[key]))
            self.fill_color_button.setEnabled(v['type'] in {'volume','brightness'}|MEMORY_TYPES);self.fill_color_button.setStyleSheet('background:'+v.get('fill_color','#a397ec')+';color:#17241f');self.name_field.setText(v['name']);self.font_field.setCurrentFont(QFont(v['font']));self.show_text.setChecked(v['show_text']);self.glow.setEnabled(v['type'] in MONITOR_TYPES);self.glow.setChecked(v.get('glow',False));self.transparent.setChecked(v['transparent']);self.target.setText(v['target']);self.color_button.setStyleSheet('background:'+v['color']+';color:#17241f')
        self.rebuilding=False
    def apply_properties(self,*_):
        if self.rebuilding:return
        v=self.selected()
        if not v:return
        for key,box in self.fields.items():v[key]=1-box.value()/100 if key.endswith('alpha') or key=='opacity' else box.value()
        v['x']=min(v['x'],960-v['w']);v['y']=min(v['y'],360-v['h']);v.update(name=self.name_field.text()[:100],font=self.font_field.currentFont().family(),show_text=self.show_text.isChecked(),glow=self.glow.isChecked(),transparent=self.transparent.isChecked(),target=self.target.text().strip());self.commit(True,v['id'])
    def commit(self,rebuild=False,selected=None):
        try:validate(self.doc)
        except Exception as e:self.message(str(e));return
        if self.history[-1]!=self.doc:self.history.append(copy.deepcopy(self.doc));self.history=self.history[-60:];self.future=[]
        if rebuild:self.rebuild(selected)
        self.autosave.start(700);self.message('已修改 · 自动保存中')
    def save_doc(self):
        try:save(self.config,self.doc);self.load_error='';self.message('方案已保存')
        except Exception as e:self.message('保存失败：'+str(e))
    def undo(self):
        if len(self.history)<2:return
        self.future.append(self.history.pop());self.doc=copy.deepcopy(self.history[-1]);self.rebuild();self.load_media();self.frame_timer.setInterval(round(1000/self.doc['fps']));self.autosave.start(700)
    def redo(self):
        if not self.future:return
        self.doc=copy.deepcopy(self.future.pop());self.history.append(copy.deepcopy(self.doc));self.rebuild();self.load_media();self.frame_timer.setInterval(round(1000/self.doc['fps']));self.autosave.start(700)
    def add_widget(self):
        kind=self.kind_select.currentData();v=widget(kind,32,32);self.doc['widgets'].append(v);self.doc['background_only']=False;self.commit(True,v['id'])
    def duplicate(self):
        v=self.selected()
        if not v:return
        n=copy.deepcopy(v);n['id']=uuid.uuid4().hex;n['x']=min(960-n['w'],n['x']+20);n['y']=min(360-n['h'],n['y']+20);self.doc['widgets'].append(n);self.commit(True,n['id'])
    def remove_widget(self):
        v=self.selected()
        if v:self.doc['widgets'].remove(v);self.commit(True)
    def reorder(self,delta):
        v=self.selected()
        if not v:return
        i=self.doc['widgets'].index(v);j=i+delta
        if 0<=j<len(self.doc['widgets']):self.doc['widgets'][i],self.doc['widgets'][j]=self.doc['widgets'][j],self.doc['widgets'][i];self.commit(True,v['id'])
    def reuse_style(self):
        v=self.selected();family={'shortcut','shutdown','restart'}
        if not v:return
        if v['type'] in MONITOR_TYPES:
            for target in self.doc['widgets']:
                if target['type'] in MONITOR_TYPES:copy_monitor_style(v,target)
        elif v['type'] in family:
            for target in self.doc['widgets']:
                if target['type'] in family:copy_style(v,target)
        else:self.message('可复用CPU/GPU四项的文字样式，或快捷/电源按钮的外观');return
        self.commit(True,v['id'])
    def choose_text_color(self):
        v=self.selected()
        if v:
            c=QColorDialog.getColor(QColor(v['color']),self,'文字颜色')
            if c.isValid():v['color']=c.name();self.commit(True,v['id'])
    def choose_fill_color(self):
        v=self.selected()
        if v and v['type'] in {'volume','brightness'}|MEMORY_TYPES:
            c=QColorDialog.getColor(QColor(v.get('fill_color','#a397ec')),self,'进度填充颜色')
            if c.isValid():v['fill_color']=c.name();self.commit(True,v['id'])
    def choose_target(self):
        p,_=QFileDialog.getOpenFileName(self,'选择程序、文件或快捷方式')
        if p:self.target.setText(p);self.apply_properties()
    def choose_folder(self):
        p=QFileDialog.getExistingDirectory(self,'选择文件夹')
        if p:self.target.setText(p);self.apply_properties()
    def import_asset(self,path):
        p=Path(path);folder=self.data/'assets';folder.mkdir(exist_ok=True);target=folder/(uuid.uuid4().hex+p.suffix.lower());shutil.copy2(p,target);return str(target)
    def choose_icon(self):
        v=self.selected()
        if not v or v['type'] not in ('shortcut','shutdown','restart'):self.message('请选择一个按钮');return
        p,_=QFileDialog.getOpenFileName(self,'选择按钮图片','','图片 (*.png *.jpg *.jpeg *.webp *.bmp *.gif)')
        if p:
            try:
                reader=QImageReader(p);size=reader.size()
                if size.width()*size.height()>36000000:raise ValueError('图片尺寸过大')
                image=reader.read()
                if image.isNull():raise ValueError('无法读取图片')
                side=min(image.width(),image.height());image=image.copy((image.width()-side)//2,(image.height()-side)//2,side,side).scaled(512,512,Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.SmoothTransformation);folder=self.data/'assets';folder.mkdir(exist_ok=True);target=folder/(uuid.uuid4().hex+'.png');image.save(str(target));v['icon']=str(target);self.commit(True,v['id'])
            except Exception as e:self.message(str(e))
    def clear_icon(self):
        v=self.selected()
        if v:v['icon']='';self.commit(True,v['id'])
    def choose_background(self):
        p,_=QFileDialog.getOpenFileName(self,'选择背景','','图片与视频 (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.mp4 *.mkv *.mov *.webm *.avi *.m4v)')
        if p:
            try:self.doc['media']=self.import_asset(p);self.load_media();self.commit()
            except Exception as e:self.message(str(e))
    def choose_bg_color(self):
        c=QColorDialog.getColor(QColor(self.doc['background']),self,'背景颜色')
        if c.isValid():self.doc['background']=c.name();self.commit();self.scene.update()
    def clear_background(self):self.doc['media']='';self.load_media();self.commit()
    def load_media(self):
        from PySide6.QtGui import QMovie
        self.player.stop()
        if self.movie:self.movie.stop();self.movie.deleteLater();self.movie=None
        self.scene.frame=None;p=self.doc['media'];self.media_label.setText(Path(p).name if p else '渐变纯色背景')
        if not p:return
        if not Path(p).is_file():self.message('背景素材丢失，请重新选择');return
        suffix=Path(p).suffix.lower()
        if suffix=='.gif':self.movie=QMovie(p);self.movie.frameChanged.connect(lambda _:self.update_gif());self.movie.start()
        elif suffix in ('.mp4','.mkv','.mov','.webm','.avi','.m4v'):self.player.setSource(QUrl.fromLocalFile(p));self.player.play()
        else:self.scene.frame=QImage(p)
        self.scene.update()
    def update_gif(self):self.scene.frame=self.movie.currentImage();self.scene.update()
    def video_frame(self,frame):
        if frame.isValid():self.scene.frame=frame.toImage();self.scene.update()
    def change_fit(self,*_):
        if not self.rebuilding:self.doc['fit']=self.fit.currentData();self.scene.update();self.commit()
    def change_fps(self,*_):
        if not self.rebuilding:self.doc['fps']=self.fps.currentData();self.frame_timer.setInterval(round(1000/self.doc['fps']));self.commit()
    def change_pure(self,value):
        if not self.rebuilding:self.doc['background_only']=value;self.commit(True)
    def change_brightness(self):self.doc['brightness']=self.brightness.value();self.scene.update();self.commit()
    def use_template(self,name):
        if QMessageBox.question(self,'替换当前布局','使用此布局？可撤销恢复当前方案。')!=QMessageBox.StandardButton.Yes:return
        self.save_doc();self.doc=document(name);self.commit(True);self.load_media();self.show_page(0)
    def export_scene(self):
        p,_=QFileDialog.getSaveFileName(self,'导出方案',self.doc['name']+'.vk03','VK03 方案 (*.vk03)')
        if p:
            try:export_bundle(p,self.doc);self.message('方案与素材已导出')
            except Exception as e:self.message(str(e))
    def import_scene(self):
        p,_=QFileDialog.getOpenFileName(self,'导入方案','','VK03 方案 (*.vk03)')
        if p:
            try:self.doc=import_bundle(p,self.data);self.commit(True);self.load_media();self.frame_timer.setInterval(round(1000/self.doc['fps']));self.show_page(0)
            except Exception as e:self.message('导入失败：'+str(e))
    def render_frame(self):
        image=QImage(960,360,QImage.Format.Format_RGB888);image.fill(QColor(self.doc['background']));p=QPainter(image);p.setRenderHint(QPainter.RenderHint.Antialiasing);self.scene.exporting=True
        try:self.scene.render(p,QRectF(0,0,960,360),QRectF(0,0,960,360))
        finally:self.scene.exporting=False;p.end()
        return image
    def tick(self):
        self.animation_time=time.monotonic();self.scene.update()
        if self.device and self.device.isRunning():self.device.submit(self.render_frame());self.stats.setText(f'目标 {self.doc["fps"]} FPS · 已发送 {self.device.count} 帧 · 最新帧队列 ≤ 1')
        if self.volume_pending is not None and time.monotonic()-self.last_volume>.065:
            n=self.volume_pending;self.volume_pending=None;self.last_volume=time.monotonic()
            if self.bridge:self.bridge.post('volume.set',{'value':n})
    def refresh_state(self):
        import psutil
        memory=psutil.virtual_memory();self.values.update(cpu=psutil.cpu_percent(),memory=memory.percent,memory_used=(memory.total-memory.available)/2**30,memory_total=memory.total/2**30)
        if self.bridge:self.bridge.post('state.get')
        self.scene.update()
    def receive_state(self,data):
        for k in ('volume','muted','media','gpu','gpu_temp','cpu_temp'):
            if k in data and not (k=='volume' and (time.monotonic()<self.volume_hold or self.volume_pending is not None or self.touch_active and self.touch_active.get('kind')=='volume')):self.values[k]=data[k]
        self.scene.update()
    def connect_device(self):
        if self.device and self.device.isRunning():self.disconnect_device();return
        if QMessageBox.question(self,'连接 VK03','请确认已完全退出 MythTool 和其他 VK03 面板，再连接屏幕。现在连接？')!=QMessageBox.StandardButton.Yes:return
        self.manual_disconnect=False;self.start_device()
    def start_device(self):
        if self.quitting or self.manual_disconnect:return
        self.device=DeviceWorker(self);self.device.status.connect(self.device_status);self.device.failure.connect(self.device_error);self.device.gesture.connect(self.gesture);self.device.finished.connect(self.device_finished);self.device.submit(self.render_frame());self.device.start();self.connect_button.setText('断开屏幕')
    def device_status(self,text):
        self.device_badge.setText('●  '+text);self.device_detail.setText(text)
        if text.startswith('已连接'):self.reconnect_armed=True
    def device_error(self,text):self.message(text);self.device_detail.setText(text)
    def device_finished(self):
        self.connect_button.setText('连接屏幕');self.touch_active=None;self.power_armed=None
        if getattr(self,'reconnect_armed',False) and self.auto_reconnect.isChecked() and not self.quitting and not self.manual_disconnect:QTimer.singleShot(3000,self.reconnect_device)
    def reconnect_device(self):
        if not self.quitting and not self.manual_disconnect and not(self.device and self.device.isRunning()):self.start_device()
    def disconnect_device(self):
        self.manual_disconnect=True;self.reconnect_armed=False
        if self.device:
            self.device.stop()
            if not self.device.wait(5000):self.message('正在等待USB传输退出…');return
        self.device=None;self.touch_active=None;self.power_armed=None;self.connect_button.setText('连接屏幕');self.device_status('未连接')
    def gesture(self,phase,x,y):
        if phase=='cancel':self.touch_active=None;return
        if self.doc['background_only']:return
        if phase=='down':
            self.touch_active=None
            for v in reversed(self.doc['widgets']):
                if v['x']<=x<=v['x']+v['w'] and v['y']<=y<=v['y']+v['h']:
                    nx=(x-v['x'])/v['w'];ny=(y-v['y'])/v['h'];self.touch_active={'id':v['id'],'kind':v['type'],'widget':v,'range':v['type'] in ('volume','brightness') and ny>.45,'mute':v['type']=='volume' and nx>.85 and ny<.45,'start':(nx,ny)};break
        a=self.touch_active
        if not a:return
        v=a['widget'];nx=(x-v['x'])/v['w'];ny=(y-v['y'])/v['h']
        if a['range']:
            n=round(max(0,min(100,(nx-.026)/.937*100)))
            if a['kind']=='volume':self.values['volume']=n;self.volume_pending=n;self.volume_hold=time.monotonic()+.8
            else:self.doc['brightness']=max(10,n);self.brightness.setValue(max(10,n))
        if phase=='up':
            self.touch_active=None
            if a['kind']=='brightness' and a['range']:self.commit()
            if not a['range'] and 0<=nx<=1 and 0<=ny<=1 and abs(nx-a['start'][0])+abs(ny-a['start'][1])<.25:self.execute_widget(v,nx,ny,a['mute'])
        self.scene.update()
    def execute_widget(self,v,x,y,mute=False):
        kind=v['type']
        if kind=='volume' and mute:
            if self.bridge:self.bridge.post('volume.muteToggle')
        elif kind=='music' and y>.62:
            index=min(3,max(0,int((x*270-17)/59)))
            if self.bridge:self.bridge.post(['media.previous','media.play','media.pause','media.next'][index])
        elif kind=='shortcut':
            from urllib.parse import urlsplit
            target=v['target']
            try:
                if target.startswith(('https://','http://')):
                    url=urlsplit(target)
                    if not url.hostname or url.username or url.password:raise ValueError('网址不正确')
                elif not Path(target).is_absolute() or not Path(target).exists():raise ValueError('快捷目标不存在')
                os.startfile(target)
            except Exception as e:self.message(str(e))
        elif kind in ('shutdown','restart'):
            now=time.monotonic()
            if not self.power_armed or self.power_armed[0]!=v['id'] or now-self.power_armed[1]>2.5:
                self.power_armed=(v['id'],now);self.message('请在2.5秒内再次点按小屏同一按钮确认'+v['name']);self.screen_message=('再次点按确认'+v['name'],now+2.5);return
            self.power_armed=None;self.screen_message=None
            if self.bridge:self.bridge.post('system.'+kind,{'confirmed':True})
    def closeEvent(self,event):
        if not self.quitting and QSystemTrayIcon.isSystemTrayAvailable():event.ignore();self.hide();self.tray.showMessage('VK03 Studio','已在托盘后台运行，右键图标可退出。');return
        self.scene.blockSignals(True);event.accept()
    def quit_app(self):
        self.quitting=True
        if not self.load_error:self.save_doc()
        self.frame_timer.stop();self.poll.stop();self.disconnect_device();self.player.stop()
        if self.bridge:self.bridge.close()
        self.tray.hide();QApplication.instance().quit()

def main():
    app=QApplication(sys.argv);app.setOrganizationName('VK03Community');app.setApplicationName('VK03Studio');app.setStyle('Fusion');app.setStyleSheet(STYLE)
    data=None
    if '--data-dir' in sys.argv:data=sys.argv[sys.argv.index('--data-dir')+1]
    folder=Path(data or QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation));folder.mkdir(parents=True,exist_ok=True)
    lock=QLockFile(str(folder/'studio.lock'))
    if not lock.tryLock(100):QMessageBox.information(None,'VK03 Studio','VK03 Studio 已在运行，请从系统托盘打开。');return
    logging.basicConfig(filename=str(folder/'studio.log'),level=logging.INFO,encoding='utf8',format='%(asctime)s %(message)s')
    def failure(kind,value,tb):
        import traceback
        logging.error(''.join(traceback.format_exception(kind,value,tb)));QMessageBox.critical(None,'VK03 Studio',str(value)+'\n详情已写入 studio.log')
    sys.excepthook=failure
    smoke='--smoke-test' in sys.argv
    window=Studio(folder,start_bridge=not smoke);window.show()
    if smoke:
        def smoke_finish():
            import json
            window.render_frame().save(str(folder/'smoke-panel.png'));window.grab().save(str(folder/'smoke-window.png'));(folder/'smoke.json').write_text(json.dumps(dict(ok=True,pages=window.pages.count(),widgets=len(window.doc['widgets']),hardwareOpened=window.device is not None)),encoding='utf8');window.quit_app()
        QTimer.singleShot(600,smoke_finish)
    result=app.exec();lock.unlock();sys.exit(result)
if __name__=='__main__':main()
