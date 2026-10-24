"""Small native Qt controls shared by the cozy hub. No application state here."""
from pathlib import Path
from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QFrame, QLabel, QPushButton, QHBoxLayout,
                              QVBoxLayout, QWidget, QSizePolicy)

BASE = Path(__file__).resolve().parents[2]
INK = '#514363'
ACCENT = '#9776c5'


def icon(name='spark', color='#9174b6'):
    pix = QPixmap(44, 44); pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.scale(2, 2)
    p.setPen(QPen(QColor(color), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    path = QPainterPath()
    if name == 'home':
        path.moveTo(2, 10); path.lineTo(11, 2); path.lineTo(20, 10)
        path.moveTo(4, 9); path.lineTo(4, 20); path.lineTo(18, 20); path.lineTo(18, 9)
        path.moveTo(8, 20); path.lineTo(8, 13); path.lineTo(14, 13); path.lineTo(14, 20)
        p.drawPath(path)
    elif name in ('clock', 'focus', 'history'):
        p.drawEllipse(QRectF(2, 2, 18, 18)); p.drawLine(11, 5, 11, 11); p.drawLine(11, 11, 16, 14)
    elif name in ('heart', 'interaction'):
        path.moveTo(11, 19); path.cubicTo(-5, 9, 5, -3, 11, 5); path.cubicTo(17, -3, 27, 9, 11, 19); p.drawPath(path)
    elif name in ('tools', 'folder'):
        path.moveTo(2, 7); path.lineTo(2, 4); path.lineTo(9, 4); path.lineTo(12, 7); path.lineTo(20, 7); path.lineTo(20, 19); path.lineTo(2, 19); path.closeSubpath(); p.drawPath(path)
    elif name in ('chart', 'usage'):
        for x,h in [(3,8),(9,16),(15,12)]: p.drawRoundedRect(QRectF(x,20-h,4,h),1,1)
    elif name in ('settings','gear'):
        p.drawEllipse(QRectF(4,4,14,14)); p.drawEllipse(QRectF(8,8,6,6))
        for a,b,c,d in [(11,1,11,4),(11,18,11,21),(1,11,4,11),(18,11,21,11),(4,4,6,6),(16,16,18,18),(4,18,6,16),(16,6,18,4)]:p.drawLine(a,b,c,d)
    elif name in ('close','delete'):
        p.drawLine(5,5,17,17);p.drawLine(17,5,5,17)
    elif name == 'plus':
        p.drawLine(11,3,11,19);p.drawLine(3,11,19,11)
    elif name == 'pause':
        p.drawLine(7,4,7,18);p.drawLine(15,4,15,18)
    elif name in ('play','next'):
        path.moveTo(7,3);path.lineTo(18,11);path.lineTo(7,19);path.closeSubpath();p.drawPath(path)
    elif name == 'check':
        p.drawLine(3,11,8,17);p.drawLine(8,17,19,5)
    elif name == 'bell':
        path.moveTo(4,16);path.lineTo(6,12);path.lineTo(6,8);path.cubicTo(6,1,16,1,16,8);path.lineTo(16,12);path.lineTo(18,16);path.closeSubpath();p.drawPath(path);p.drawLine(9,19,13,19)
    elif name == 'edit':
        path.moveTo(3,19);path.lineTo(5,13);path.lineTo(15,3);path.lineTo(19,7);path.lineTo(9,17);path.closeSubpath();p.drawPath(path)
    elif name == 'eye':
        path.moveTo(1,11);path.cubicTo(7,1,15,1,21,11);path.cubicTo(15,21,7,21,1,11);p.drawPath(path);p.drawEllipse(QRectF(8,8,6,6))
    else:
        path.moveTo(11,1);path.lineTo(14,8);path.lineTo(21,11);path.lineTo(14,14);path.lineTo(11,21);path.lineTo(8,14);path.lineTo(1,11);path.lineTo(8,8);path.closeSubpath();p.drawPath(path)
    p.end();pix.setDevicePixelRatio(2)
    return QIcon(pix)


def label(text='', role='', wrap=True):
    obj=QLabel(str(text));obj.setProperty('role',role);obj.setWordWrap(wrap)
    obj.setTextFormat(Qt.TextFormat.PlainText)
    return obj


def button(text, icon='spark', primary=False):
    b=QPushButton(str(text));b.setProperty('primary',primary);b.setIcon(globals()['icon'](icon,'#ffffff' if primary else '#9174b6'))
    b.setIconSize(QSize(19,19));b.setMinimumHeight(36);b.setCursor(Qt.CursorShape.PointingHandCursor);b.setAccessibleName(str(text))
    return b


def row(*widgets):
    w=QWidget();l=QHBoxLayout(w);l.setContentsMargins(0,0,0,0);l.setSpacing(8)
    for obj in widgets:l.addWidget(obj)
    return w


def clear_layout(layout):
    while layout.count():
        item=layout.takeAt(0)
        if item.widget(): item.widget().deleteLater()
        elif item.layout(): clear_layout(item.layout())


def duration(seconds):
    seconds=max(0,int(seconds or 0));h,rem=divmod(seconds,3600);m,s=divmod(rem,60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m:02d}:{s:02d}'


class Card(QFrame):
    def __init__(self,title='',parent=None):
        super().__init__(parent);self.setObjectName('cozyCard')
        self.layout=QVBoxLayout(self);self.layout.setContentsMargins(14,12,14,12);self.layout.setSpacing(8)
        if title:self.layout.addWidget(label(title,'cardTitle'))


class Scene(QWidget):
    """Aspect-preserving static page illustration; text is always a real widget."""
    def __init__(self,kind='home',caption='',compact=False,parent=None):
        super().__init__(parent);self.kind=kind;self.compact=compact;self.pixmap=QPixmap();self.setMinimumHeight(110 if compact else 270)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        self.caption=label(caption,'speech');self.caption.setObjectName('sceneSpeech');self.caption.setMaximumWidth(240);self.caption.setMinimumWidth(185);self.caption.setMinimumHeight(70 if compact else 76)
        l=QVBoxLayout(self);l.setContentsMargins(145 if compact else 20,8 if compact else 18,20,8 if compact else 18);l.addWidget(self.caption,0,Qt.AlignmentFlag.AlignLeft if compact else Qt.AlignmentFlag.AlignRight);l.addStretch()
        self.load_art()

    def load_art(self):
        path=BASE/'assets'/'ui'/'scenes'/f'{self.kind}.png'
        if not path.exists():path=BASE/'assets'/'ui'/'app-icon.png'
        self.pixmap.load(str(path));self.update()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        path=QPainterPath();path.addRoundedRect(QRectF(self.rect()),20,20);p.setClipPath(path)
        p.fillRect(self.rect(),QColor('#fffaf4'))
        if not self.pixmap.isNull():
            source=QRectF(0,140,self.pixmap.width(),850) if self.compact else QRectF(0,130,1050,1000);factor=min(self.width()/source.width(),self.height()/source.height())
            # Cover without stretching. The source artwork is intentionally free of UI.
            w,h=source.width()*factor,source.height()*factor
            p.drawPixmap(QRectF(0,(self.height()-h)/2,w,h),self.pixmap,QRectF(source))
        p.end()


class CardColumns(QWidget):
    """Two desktop columns; stack complete cards on small windows."""
    def __init__(self,*cards,breakpoint=760,parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QGridLayout
        self.cards=cards;self.breakpoint=breakpoint;self.columns=0
        self.grid=QGridLayout(self);self.grid.setContentsMargins(0,0,0,0);self.grid.setSpacing(12)
        self.reflow(2)
    def reflow(self,columns):
        if columns==self.columns:return
        self.columns=columns
        for card in self.cards:self.grid.removeWidget(card)
        for i,card in enumerate(self.cards):self.grid.addWidget(card,i//columns,i%columns)
        self.grid.setColumnStretch(0,1);self.grid.setColumnStretch(1,1 if columns==2 else 0)
    def resizeEvent(self,event):
        available=self.window().width()-214 if self.window() is not self else event.size().width()
        self.reflow(2 if available>=self.breakpoint else 1)
        super().resizeEvent(event)
