import tkinter as tk
from tkinter import ttk, messagebox

BG = '#F4F6FB'
INK = '#273149'
MUTED = '#78849A'
ACCENT = '#6175DA'


def style(root):
    s = ttk.Style(root)
    s.theme_use('clam')
    s.configure('.', font=('Microsoft YaHei UI', 10), background=BG, foreground=INK)
    s.configure('TFrame', background=BG)
    s.configure('TLabel', background=BG)
    s.configure('Title.TLabel', font=('Microsoft YaHei UI', 20, 'bold'))
    s.configure('Muted.TLabel', foreground=MUTED)
    s.configure('TButton', padding=(12, 7), background='#E7EBFA', borderwidth=0)
    s.map('TButton', background=[('active', '#D9E0FF')])
    s.configure('Accent.TButton', background=ACCENT, foreground='white')
    s.map('Accent.TButton', background=[('active', '#4E61C0')])
    s.configure('Treeview', rowheight=31, background='white', fieldbackground='white', borderwidth=0)
    s.configure('Treeview.Heading', padding=8, background='#E9EDF7')
    s.configure('TNotebook', background=BG, borderwidth=0)
    s.configure('TNotebook.Tab', padding=(16, 9))
    s.map('TNotebook.Tab', background=[('selected', 'white')])
    s.configure('TEntry', padding=7)


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
