import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox

BG = '#F5F6F1'
UI_FONT = 'Microsoft YaHei UI'
CARD = '#FFFEFA'
SOFT = '#F1F4EE'
BORDER = '#DDE5DA'
INK = '#2D3B36'
MUTED = '#627269'
ACCENT = '#4F7668'
HOVER = '#E6EEE6'


def fit_text(text, measure, max_width):
    """Fit one line by measured pixels, not by an assumed character width."""
    text = ' '.join(str(text).split())
    if max_width <= 0:
        return ''
    if measure(text) <= max_width:
        return text
    ellipsis = '…'
    if measure(ellipsis) > max_width:
        return ''
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if measure(text[:middle] + ellipsis) <= max_width:
            low = middle
        else:
            high = middle - 1
    return text[:low] + ellipsis


def draw_icon(canvas, x, y, name, size=18, color=ACCENT):
    """Draw small line icons with Canvas primitives, independent of fonts."""
    scale = size / 20
    def points(values):
        return [x + value * scale if index % 2 == 0 else y + value * scale
                for index, value in enumerate(values)]
    def line(values, **kw):
        return canvas.create_line(*points(values), fill=color, width=1.6,
                                  capstyle='round', joinstyle='round', **kw)
    def oval(values, **kw):
        return canvas.create_oval(*points(values), outline=color, width=1.6, **kw)
    if name == 'home':
        line([2, 9, 10, 2, 18, 9])
        line([4, 8, 4, 18, 8, 18, 8, 12, 12, 12, 12, 18, 16, 18, 16, 8])
    elif name == 'heart':
        line([10, 17, 3, 10, 2, 6, 5, 3, 8, 3, 10, 6,
              12, 3, 15, 3, 18, 6, 17, 10, 10, 17], smooth=True)
    elif name == 'clock':
        oval([3, 4, 17, 18])
        line([10, 7, 10, 11, 13, 13])
        line([8, 1, 12, 1])
    elif name == 'bolt':
        line([11, 1, 3, 11, 9, 11, 8, 19, 17, 8, 11, 8, 11, 1])
    elif name == 'chart':
        line([2, 2, 2, 18, 18, 18])
        for left, top in ((6, 10), (11, 5), (16, 8)):
            canvas.create_line(
                *points([left, 15, left, top]), fill=color, width=3, capstyle='round')
    elif name == 'settings':
        oval([4, 4, 16, 16])
        oval([8, 8, 12, 12])
        for values in ([10, 1, 10, 4], [10, 16, 10, 19], [1, 10, 4, 10],
                       [16, 10, 19, 10], [3, 3, 5, 5], [15, 15, 17, 17],
                       [3, 17, 5, 15], [15, 5, 17, 3]):
            line(values)
    elif name == 'bell':
        line([4, 14, 5, 11, 5, 7, 7, 3, 13, 3, 15, 7, 15, 11, 16, 14], smooth=True)
        line([3, 15, 17, 15])
        line([8, 18, 12, 18])
    elif name == 'check':
        line([3, 10, 8, 15, 17, 5])
    elif name == 'circle':
        oval([3, 3, 17, 17])
    elif name == 'chevron':
        line([7, 4, 13, 10, 7, 16])
    else:
        line([10, 1, 12, 8, 19, 10, 12, 12, 10, 19, 8, 12, 1, 10, 8, 8, 10, 1])


class RoundedButton(tk.Canvas):
    """Small rounded button with mouse, keyboard, disabled and focus states."""
    def __init__(self, parent, text, command, primary=False, quiet=False):
        self.text, self.command = text, command
        self.primary, self.quiet = primary, quiet
        self.state, self.hover, self.focused = 'normal', False, False
        self.foreground = 'white' if primary else ACCENT
        self._button_font = tkfont.Font(parent, family=UI_FONT, size=9)
        super().__init__(parent, bg=parent.cget('bg'), highlightthickness=0,
                         bd=0, takefocus=True, cursor='hand2',
                         width=self._button_font.measure(text) + 28,
                         height=max(34, self._button_font.metrics('linespace') + 14))
        self.bind('<Configure>', lambda event: self._draw())
        self.bind('<Enter>', lambda event: self._set_hover(True))
        self.bind('<Leave>', lambda event: self._set_hover(False))
        self.bind('<FocusIn>', lambda event: self._set_focus(True))
        self.bind('<FocusOut>', lambda event: self._set_focus(False))
        self.bind('<Button-1>', self._activate)
        self.bind('<Return>', self._activate)
        self.bind('<space>', self._activate)
        self._draw()

    def _set_hover(self, value):
        self.hover = value
        self._draw()

    def _set_focus(self, value):
        self.focused = value
        self._draw()

    def _activate(self, event=None):
        if self.state != 'disabled':
            self.focus_set()
            self.invoke()
        return 'break'

    def invoke(self):
        if self.state != 'disabled':
            return self.command()

    def configure(self, cnf=None, **kwargs):
        custom = {'text': self.text, 'state': self.state, 'fg': self.foreground}
        if not kwargs and isinstance(cnf, str):
            if cnf in custom:
                return (cnf, cnf, cnf.title(), '', custom[cnf])
            return super().configure(cnf)
        if cnf is None and not kwargs:
            options = super().configure()
            options.update({key: (key, key, key.title(), '', value)
                            for key, value in custom.items()})
            return options
        if cnf is not None:
            kwargs.update(cnf)
        redraw = False
        for key, attribute in (('text', 'text'), ('state', 'state'), ('fg', 'foreground')):
            if key in kwargs:
                setattr(self, attribute, kwargs.pop(key))
                redraw = True
        if redraw:
            kwargs.setdefault('width', self._button_font.measure(self.text) + 28)
            kwargs['takefocus'] = self.state != 'disabled'
            kwargs['cursor'] = 'arrow' if self.state == 'disabled' else 'hand2'
        result = super().configure(**kwargs) if kwargs else None
        if redraw:
            self._draw()
        return result

    config = configure

    def cget(self, key):
        if key in ('text', 'state', 'fg'):
            return {'text': self.text, 'state': self.state, 'fg': self.foreground}[key]
        return super().cget(key)

    __getitem__ = cget

    def _draw(self):
        self.delete('all')
        width = max(2, self.winfo_width())
        height = max(2, self.winfo_height())
        if width <= 2:
            width, height = int(super().cget('width')), int(super().cget('height'))
        disabled = self.state == 'disabled'
        fill = (BORDER if disabled else '#406555' if self.hover else ACCENT) if self.primary else (
            HOVER if self.hover and not disabled else self.cget('bg') if self.quiet else SOFT)
        def rounded(inset, color):
            radius = min(12, (height - inset * 2) / 2)
            x1, y1, x2, y2 = inset, inset, width - inset, height - inset
            self.create_polygon(x1 + radius, y1, x2 - radius, y1, x2, y1,
                x2, y1 + radius, x2, y2 - radius, x2, y2, x2 - radius, y2,
                x1 + radius, y2, x1, y2, x1, y2 - radius, x1, y1 + radius,
                x1, y1, smooth=True, fill=color, outline='')
        rounded(1, INK if self.focused and not disabled else fill)
        rounded(3, fill)
        self.create_text(width / 2, height / 2,
                         text=fit_text(self.text, self._button_font.measure, width - 20),
                         font=self._button_font, fill=MUTED if disabled else self.foreground)


def text_button(parent, text, command, *, primary=False, quiet=False):
    return RoundedButton(parent, text, command, primary, quiet)


def style(root):
    s = ttk.Style(root)
    s.theme_use('clam')
    s.configure('.', font=(UI_FONT, 10), background=BG, foreground=INK)
    s.configure('TFrame', background=BG)
    s.configure('TLabel', background=BG)
    s.configure('Title.TLabel', font=('Microsoft YaHei UI', 20, 'bold'))
    s.configure('Muted.TLabel', foreground=MUTED)
    s.configure('TButton', padding=(12, 8), background='#E8EEE5', borderwidth=1,
                bordercolor=BORDER, focuscolor=ACCENT)
    s.map('TButton', background=[('disabled', '#EEF1EB'), ('active', HOVER)],
          foreground=[('disabled', '#929BAB')], bordercolor=[('focus', ACCENT)])
    s.configure('Accent.TButton', background=ACCENT, foreground='white')
    s.map('Accent.TButton', background=[('disabled', '#DDE5DA'), ('active', '#406555')],
          foreground=[('disabled', MUTED), ('!disabled', 'white')])
    s.configure('Treeview', rowheight=31, background='white', fieldbackground='white', borderwidth=0)
    s.configure('Treeview.Heading', padding=8, background='#E9EEE5')
    s.map('Treeview', background=[('selected', '#DEE9DD')],
          foreground=[('selected', INK)])
    s.configure('TNotebook', background=BG, borderwidth=0)
    s.configure('TNotebook.Tab', padding=(16, 9))
    s.map('TNotebook.Tab', background=[('selected', CARD)],
          foreground=[('selected', ACCENT)])
    s.configure('TEntry', padding=7, bordercolor=BORDER)
    s.map('TEntry', bordercolor=[('focus', ACCENT)])


def heading(parent, title, subtitle=''):
    ttk.Label(parent, text=title, font=('Microsoft YaHei UI', 15, 'bold')).pack(anchor='w', pady=(0, 4))
    if subtitle:
        ttk.Label(parent, text=subtitle, style='Muted.TLabel', wraplength=720).pack(anchor='w', pady=(0, 15))


def table(parent, columns, widths=None):
    frame = ttk.Frame(parent)
    frame.pack(fill='both', expand=True, pady=6)
    tree = ttk.Treeview(frame, columns=columns, show='headings', selectmode='browse', height=8)
    for i, col in enumerate(columns):
        tree.heading(col, text=col)
        tree.column(col, width=(widths or [150] * len(columns))[i], anchor='w')
    scroll = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side='left', fill='both', expand=True)
    scroll.pack(side='right', fill='y')
    return tree


def buttons(parent, items):
    row = ttk.Frame(parent)
    row.pack(fill='x', pady=8)
    for title, command in items:
        ttk.Button(row, text=title, command=command).pack(side='left', padx=(0, 8))
    return row


def safe(parent, callback):
    try:
        callback()
    except Exception as exc:
        messagebox.showerror('操作未完成', str(exc), parent=parent)


def duration(seconds):
    minutes = int(seconds // 60)
    return f'{minutes // 60}小时{minutes % 60:02d}分' if minutes >= 60 else f'{minutes}分{int(seconds % 60):02d}秒'


class PetArt:
    """Replaceable original vector character; no external art dependency."""
    def __init__(self, canvas):
        self.canvas = canvas

    def draw(self, tick, focused=False, accent='#778EE3'):
        c = self.canvas
        c.delete('all')
        blink = tick % 90 in (0, 1)
        bob = 1 if tick % 16 < 8 else -1
        def oval(box, fill, outline='', width=1):
            c.create_oval(*box, fill=fill, outline=outline, width=width)
        def poly(points, fill, outline=''):
            c.create_polygon(points, fill=fill, outline=outline, smooth=True)
        oval((43, 163, 137, 172), '#D7DEF1')
        # Long hair, two curled tails, compact chibi proportions.
        poly([49, 53, 30, 70, 32, 124, 20, 142, 55, 147, 64, 102], accent)
        poly([126, 53, 146, 76, 147, 124, 162, 143, 125, 146, 115, 102], accent)
        oval((47, 29+bob, 134, 122+bob), '#4B609A')
        oval((58, 136, 81, 165), '#FFDDCF')
        oval((99, 136, 122, 165), '#FFDDCF')
        oval((53, 158, 82, 170), '#38445F')
        oval((98, 158, 127, 170), '#38445F')
        poly([65, 103, 115, 103, 133, 148, 91, 159, 47, 148], '#40557F')
        poly([72, 108, 107, 108, 117, 147, 89, 153, 63, 147], '#F8FAFF')
        oval((39, 110+bob, 62, 132+bob), '#FFDDCF')
        oval((118, 110+bob, 141, 132+bob), '#FFDDCF')
        oval((53, 42+bob, 128, 110+bob), '#FFE9DC')
        poly([50, 62+bob, 55, 27+bob, 93, 19+bob, 134, 41+bob, 130, 79+bob, 110, 51+bob, 100, 71+bob, 86, 46+bob, 66, 70+bob], accent)
        for x,y in [(58,31),(70,24),(83,21),(96,21),(109,26),(121,34)]:
            oval((x-7,y-5+bob,x+9,y+8+bob), '#F9FBFF')
        for x in (74, 108):
            if blink:
                c.create_line(x-6, 82+bob, x+6, 82+bob, fill='#35446D', width=3)
            else:
                oval((x-7,72+bob,x+6,91+bob), '#334E82')
                oval((x-4,74+bob,x+1,80+bob), 'white')
            oval((x-10,91+bob,x+5,96+bob), '#F8BAC1')
        c.create_arc(84, 89+bob, 98, 101+bob, start=200, extent=140, style='arc', outline='#AC6B7F', width=2)
        poly([83,108,72,103,74,118,88,112,105,103,105,118], '#99B9EF')
        oval((85,107,95,116), '#D8E8FF')
        c.create_text(90, 135, text='✦', font=('Segoe UI', 15), fill=accent)
        oval((132, 26, 144, 38), '#7CBBA7' if focused else '#A9B7D7')
        c.create_text(90, 186, text='专注中' if focused else '小汐 · 点击打开', fill='#60708E', font=('Microsoft YaHei UI', 9))
