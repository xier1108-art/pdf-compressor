"""
Main application window — redesigned.
Warm beige / terracotta design system (matches the handoff mockup).
"""

import os
import re
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core.utils import format_size, get_output_path, ensure_dir
from core.compressor import compress_pdf, find_ghostscript

# ─── Design tokens (mirrors app.css) ────────────────────────────────────────
BG_WINDOW   = "#ffffff"
BG_TITLEBAR = "#f8f8f8"
BG_HEADER   = "#fff6f3"
BG_LIST_HDR = "#fbf9f6"
BG_ACTION   = "#f7f4ef"
BG_SUBTLE   = "#faf8f5"
BG_PANEL    = "#ffffff"

INK_900 = "#1a1814"
INK_700 = "#3a342c"
INK_500 = "#7a7367"
INK_400 = "#9b9388"
INK_300 = "#c7bfb2"
INK_200 = "#e5ded0"
INK_100 = "#eeeae2"
INK_50  = "#f6f3ed"

ACCENT      = "#e05543"
ACCENT_DK   = "#c73a28"
ACCENT_TINT = "#fef4f1"
ACCENT_SOFT = "#fdece8"

SUCCESS     = "#3f8f5e"
SUCCESS_BG  = "#f0faf3"
SUCCESS_DK  = "#1f5237"
SUCCESS_MID = "#3d6b51"
SUCCESS_BRD = "#d5ead9"

APP_VERSION = "v1.5.0"
FONT = "Malgun Gothic"
MONO = "Consolas"

WIN_W = 760
WIN_H = 640


class MainWindow:
    def __init__(self, root: tk.Tk, has_dnd: bool = False):
        self.root     = root
        self.has_dnd  = has_dnd
        self.files: dict = {}          # path → {original_size, compressed_size, tree_id}
        self.output_dir = os.path.join(os.path.expanduser("~"), "Desktop", "PDF압축결과")
        self.mode    = tk.StringVar(value="recommended")
        self.is_compressing = False
        self._dot_anim_id   = None

        gs = find_ghostscript()
        self._has_gs = bool(gs)
        self._gs_ver = self._detect_gs_ver(gs) if gs else None

        self._setup_window()
        self._setup_style()
        self._build_layout()

    # ── Utilities ────────────────────────────────────────────────────────────

    @staticmethod
    def _detect_gs_ver(gs_path: str) -> str:
        try:
            import subprocess
            r = subprocess.run([gs_path, "--version"],
                               capture_output=True, text=True, timeout=3)
            m = re.search(r"(\d+\.\d+[\.\d]*)", r.stdout)
            return f"v{m.group(1)}" if m else "v10"
        except Exception:
            return "v10"

    @staticmethod
    def _shorten_path(path: str, max_len: int = 46) -> str:
        return path if len(path) <= max_len else "…" + path[-(max_len - 1):]

    # ── Window / style ───────────────────────────────────────────────────────

    def _setup_window(self):
        self.root.title("PDF 압축기")
        self.root.geometry(f"{WIN_W}x{WIN_H}")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_WINDOW)
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{WIN_W}x{WIN_H}+{(sw - WIN_W) // 2}+{(sh - WIN_H) // 2}")

    def _setup_style(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")

        s.configure("Files.Treeview",
                    background=BG_PANEL, foreground=INK_700,
                    fieldbackground=BG_PANEL,
                    font=(FONT, 9), rowheight=26,
                    borderwidth=0, relief="flat")
        s.configure("Files.Treeview.Heading",
                    background=BG_LIST_HDR, foreground=INK_500,
                    font=(FONT, 8, "bold"),
                    relief="flat", borderwidth=0)
        s.map("Files.Treeview",
              background=[("selected", ACCENT_TINT)],
              foreground=[("selected", INK_900)])
        s.map("Files.Treeview.Heading",
              background=[("active", BG_LIST_HDR)],
              relief=[("active", "flat")])
        s.layout("Files.Treeview",
                 [("Treeview.treearea", {"sticky": "nswe"})])

        s.configure("Accent.Horizontal.TProgressbar",
                    background=ACCENT, troughcolor=INK_100,
                    borderwidth=0, thickness=6)

    # ── Master layout ────────────────────────────────────────────────────────

    def _build_layout(self):
        # Pack bottom-anchored elements FIRST so they reserve space correctly.
        self._build_status_rail()         # very bottom
        self._build_bottom_container()    # above status rail (holds swapping panels)

        # Then top-anchored elements
        self._build_titlebar()            # thin strip at top
        self._build_app_header()          # brand + engine badge

        # Main scrollable-ish area (fills remaining space)
        wrap = tk.Frame(self.root, bg=BG_WINDOW)
        wrap.pack(fill="both", expand=True)
        self.content = tk.Frame(wrap, bg=BG_WINDOW, padx=24)
        self.content.pack(fill="both", expand=True, pady=(16, 12))

        self._build_drop_zone()
        self._build_file_list()
        self._build_quality_panel()

    # ── Titlebar ─────────────────────────────────────────────────────────────

    def _build_titlebar(self):
        bar = tk.Frame(self.root, bg=BG_TITLEBAR, height=32)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # PDF icon (canvas)
        ic = tk.Canvas(bar, width=14, height=14,
                       bg=BG_TITLEBAR, highlightthickness=0)
        ic.pack(side="left", padx=(10, 0), pady=9)
        ic.create_rectangle(0, 0, 10, 13, fill=ACCENT, outline="")
        ic.create_polygon(7, 0, 10, 0, 10, 4, 7, 4, fill=BG_TITLEBAR, outline="")
        ic.create_polygon(7, 0, 10, 4, 7, 4, fill=INK_300, outline="")

        tk.Label(bar, text="PDF 압축기",
                 bg=BG_TITLEBAR, fg=INK_700,
                 font=(FONT, 9)).pack(side="left", padx=7)

        # Window control buttons (decorative — X is wired to destroy)
        specs = [("─", BG_TITLEBAR, INK_900, None),
                 ("□", BG_TITLEBAR, INK_900, None),
                 ("✕", "#e81123",   "white", self.root.destroy)]
        for sym, h_bg, h_fg, cmd in specs:
            b = tk.Label(bar, text=sym, bg=BG_TITLEBAR, fg=INK_500,
                         font=(FONT, 9), width=4, cursor="hand2")
            b.pack(side="right", ipady=5)
            b.bind("<Enter>",    lambda e, w=b, hb=h_bg, hf=h_fg: w.configure(bg=hb, fg=hf))
            b.bind("<Leave>",    lambda e, w=b: w.configure(bg=BG_TITLEBAR, fg=INK_500))
            if cmd:
                b.bind("<Button-1>", lambda e, fn=cmd: fn())

        tk.Frame(self.root, bg=INK_100, height=1).pack(fill="x")

    # ── App header band ──────────────────────────────────────────────────────

    def _build_app_header(self):
        hdr = tk.Frame(self.root, bg=BG_HEADER)
        hdr.pack(fill="x")

        inner = tk.Frame(hdr, bg=BG_HEADER)
        inner.pack(fill="x", padx=24, pady=(14, 12))

        # Brand (left)
        brand = tk.Frame(inner, bg=BG_HEADER)
        brand.pack(side="left")

        mark = tk.Canvas(brand, width=36, height=36,
                         bg=BG_HEADER, highlightthickness=0)
        mark.pack(side="left", padx=(0, 10))
        mark.create_rectangle(0, 0, 36, 36, fill=ACCENT, outline="")
        # White doc shape
        mark.create_rectangle(8,  5, 22, 30, fill="white", outline="")
        mark.create_polygon(19, 5, 27, 13, 22, 30,  8, 30,  8,  5,
                            fill="#fde0db", outline="")
        mark.create_rectangle(8, 18, 28, 27, fill=ACCENT, outline="")
        mark.create_text(18, 23, text="PDF", fill="white",
                         font=(FONT, 5, "bold"))

        tf = tk.Frame(brand, bg=BG_HEADER)
        tf.pack(side="left")
        tk.Label(tf, text="PDF 압축기",
                 bg=BG_HEADER, fg=INK_900,
                 font=(FONT, 13, "bold")).pack(anchor="w")
        tk.Label(tf, text="오프라인 · 원본 보존 · 배치 처리",
                 bg=BG_HEADER, fg=INK_500,
                 font=(FONT, 8)).pack(anchor="w", pady=(2, 0))

        # Engine badge (right)
        if self._has_gs:
            badge_bg = INK_900
            badge_txt = f"⚡ Ghostscript  {self._gs_ver}" if self._gs_ver else "⚡ Ghostscript"
            badge_fg = "#f8f4ed"
        else:
            badge_bg = "#555555"
            badge_txt = "PyMuPDF fallback"
            badge_fg = "white"

        badge = tk.Frame(inner, bg=badge_bg)
        badge.pack(side="right")
        tk.Label(badge, text=badge_txt,
                 bg=badge_bg, fg=badge_fg,
                 font=(FONT, 8, "bold"),
                 padx=10, pady=5).pack()

        tk.Frame(self.root, bg=INK_100, height=1).pack(fill="x")

    # ── Drop zone ────────────────────────────────────────────────────────────

    def _build_drop_zone(self):
        self.drop_canvas = tk.Canvas(self.content, height=84,
                                     bg=ACCENT_TINT, highlightthickness=0,
                                     cursor="hand2")
        self.drop_canvas.pack(fill="x", pady=(0, 14))
        self._draw_drop_zone(active=False)

        self.drop_canvas.bind("<Button-1>",  lambda _e: self._browse_files())
        self.drop_canvas.bind("<Enter>",     lambda _e: self._draw_drop_zone(active=True))
        self.drop_canvas.bind("<Leave>",     lambda _e: self._draw_drop_zone(active=False))
        self.drop_canvas.bind("<Configure>", lambda _e: self._draw_drop_zone(
            active=False))

        if self.has_dnd:
            try:
                from tkinterdnd2 import DND_FILES
                self.drop_canvas.drop_target_register(DND_FILES)
                self.drop_canvas.dnd_bind("<<Drop>>", self._on_dnd_drop)
                self.drop_canvas.dnd_bind("<<DragEnter>>",
                                          lambda _e: self._draw_drop_zone(active=True))
                self.drop_canvas.dnd_bind("<<DragLeave>>",
                                          lambda _e: self._draw_drop_zone(active=False))
            except Exception:
                pass

    def _draw_drop_zone(self, *, active: bool):
        c = self.drop_canvas
        c.update_idletasks()
        w = c.winfo_width() or (WIN_W - 48)
        h = 84
        c.delete("all")

        bg     = "#fdece7" if active else ACCENT_TINT
        border = ACCENT   if active else "#f0a99f"
        c.configure(bg=bg)
        c.create_rectangle(2, 2, w - 2, h - 2,
                           outline=border, width=2, dash=(8, 4), fill=bg)

        cx = w // 2
        # Plus circle
        c.create_oval(cx - 18, 10, cx + 18, 46,
                      fill="white", outline=border, width=1)
        c.create_line(cx, 22, cx, 34, fill=ACCENT, width=2, capstyle="round")
        c.create_line(cx - 6, 28, cx + 6, 28, fill=ACCENT, width=2, capstyle="round")

        c.create_text(cx, 57,
                      text="PDF 파일을 드래그하거나  클릭  하여 선택",
                      font=(FONT, 9, "bold"), fill=INK_900)
        c.create_text(cx, 72,
                      text="🔒 원본 파일은 변경되지 않습니다  ·  여러 파일 선택 가능",
                      font=(FONT, 8), fill=INK_500)

    # ── File list ────────────────────────────────────────────────────────────

    def _build_file_list(self):
        # Section header
        sh = tk.Frame(self.content, bg=BG_WINDOW)
        sh.pack(fill="x", pady=(0, 6))
        tk.Label(sh, text="파일 목록",
                 bg=BG_WINDOW, fg=INK_700,
                 font=(FONT, 8, "bold")).pack(side="left")
        self.count_lbl = tk.Label(sh, text="0개 파일",
                                   bg=BG_WINDOW, fg=INK_500,
                                   font=(FONT, 8))
        self.count_lbl.pack(side="right")

        # Border wrapper (1 px INK_100)
        wrap = tk.Frame(self.content, bg=INK_100)
        wrap.pack(fill="x")
        inner = tk.Frame(wrap, bg=BG_PANEL)
        inner.pack(fill="both", padx=1, pady=1)

        cols = ("filename", "original", "compressed", "ratio")
        self.tree = ttk.Treeview(inner, columns=cols,
                                  show="headings",
                                  style="Files.Treeview",
                                  height=6)
        self.tree.heading("filename",   text="파일명",   anchor="w")
        self.tree.heading("original",   text="원본 크기", anchor="e")
        self.tree.heading("compressed", text="압축 크기", anchor="e")
        self.tree.heading("ratio",      text="압축률",   anchor="e")

        self.tree.column("filename",   width=370, anchor="w",  stretch=True)
        self.tree.column("original",   width=88,  anchor="e",  stretch=False)
        self.tree.column("compressed", width=88,  anchor="e",  stretch=False)
        self.tree.column("ratio",      width=88,  anchor="e",  stretch=False)

        # Color tags
        self.tree.tag_configure("pending", foreground=INK_300)
        self.tree.tag_configure("done",    foreground=INK_700)
        self.tree.tag_configure("ratio_ok", foreground=SUCCESS)
        self.tree.tag_configure("error",   foreground=ACCENT)

        sb = ttk.Scrollbar(inner, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.tree.bind("<Delete>", self._remove_selected)

        # Hint
        hint = tk.Frame(self.content, bg=BG_WINDOW)
        hint.pack(fill="x", pady=(3, 0))
        tk.Label(hint, text="Del 키로 목록에서 제거",
                 bg=BG_WINDOW, fg=INK_400,
                 font=(FONT, 8)).pack(anchor="e")

    # ── Quality panel ────────────────────────────────────────────────────────

    QUALITY_OPTIONS = [
        ("extreme",     "최대 압축", "900px · Q35",  "70–90%"),
        ("recommended", "권장",      "1600px · Q65", "40–70%"),
        ("low",         "저압축",    "2400px · Q85", "20–40%"),
    ]

    def _build_quality_panel(self):
        outer = tk.Frame(self.content, bg=BG_WINDOW)
        outer.pack(fill="x", pady=(10, 0))

        tk.Label(outer, text="압축 수준",
                 bg=BG_WINDOW, fg=INK_700,
                 font=(FONT, 8, "bold")).pack(side="left", padx=(0, 14))

        seg = tk.Frame(outer, bg=INK_50, padx=4, pady=4)
        seg.pack(side="left", fill="x", expand=True)

        self._q_cards: dict = {}
        for i, (qid, name, spec, est) in enumerate(self.QUALITY_OPTIONS):
            pad_r = 5 if i < 2 else 0

            # Outer card frame — its bg acts as the border color when active
            oc = tk.Frame(seg, bg=INK_50)
            oc.pack(side="left", fill="both", expand=True, padx=(0, pad_r))

            # Inner card frame — 1 px inset from oc
            ic = tk.Frame(oc, bg=INK_50, padx=8, pady=8, cursor="hand2")
            ic.pack(fill="both", expand=True, padx=1, pady=1)

            top = tk.Frame(ic, bg=INK_50)
            top.pack(fill="x")

            dot = tk.Canvas(top, width=8, height=8,
                            bg=INK_50, highlightthickness=0)
            dot.pack(side="left", padx=(0, 5), pady=3)
            dot.create_oval(0, 0, 8, 8, fill=INK_200, outline="")

            nm  = tk.Label(top, text=name, bg=INK_50, fg=INK_900,
                           font=(FONT, 9, "bold"))
            nm.pack(side="left")

            sp  = tk.Label(ic, text=spec, bg=INK_50, fg=INK_500,
                           font=(MONO, 8))
            sp.pack(anchor="w", pady=(2, 0))

            es  = tk.Label(ic, text=f"예상 감소 {est}", bg=INK_50, fg=INK_400,
                           font=(FONT, 7))
            es.pack(anchor="w", pady=(3, 0))

            self._q_cards[qid] = dict(outer=oc, inner=ic, top=top, dot=dot,
                                       nm=nm, sp=sp, es=es)

            all_widgets = [ic, top, nm, sp, es]
            for w in all_widgets:
                w.bind("<Button-1>", lambda e, q=qid: self._set_quality(q))
                w.bind("<Enter>",    lambda e, q=qid: self._q_hover(q, True))
                w.bind("<Leave>",    lambda e, q=qid: self._q_hover(q, False))

        self._update_quality_ui()

    def _set_quality(self, qid: str):
        self.mode.set(qid)
        self._update_quality_ui()

    def _q_hover(self, qid: str, entering: bool):
        if qid == self.mode.get():
            return
        bg = "#edeae3" if entering else INK_50
        c  = self._q_cards[qid]
        for w in [c["inner"], c["top"], c["nm"], c["sp"], c["es"]]:
            if w.winfo_exists():
                w.configure(bg=bg)
        if c["dot"].winfo_exists():
            c["dot"].configure(bg=bg)

    def _update_quality_ui(self):
        sel = self.mode.get()
        for qid, c in self._q_cards.items():
            active = qid == sel
            if active:
                c["outer"].configure(bg=ACCENT)           # 1 px accent border
                inner_bg = BG_PANEL
                dot_fill = ACCENT
                es_fg    = INK_700
            else:
                c["outer"].configure(bg=INK_50)
                inner_bg = INK_50
                dot_fill = INK_200
                es_fg    = INK_400

            for w in [c["inner"], c["top"], c["nm"], c["sp"]]:
                if w.winfo_exists():
                    w.configure(bg=inner_bg)
            c["es"].configure(bg=inner_bg, fg=es_fg)
            c["dot"].configure(bg=inner_bg)
            c["dot"].delete("all")
            c["dot"].create_oval(0, 0, 8, 8, fill=dot_fill, outline="")

    # ── Bottom container + three swapping panels ──────────────────────────────

    def _build_bottom_container(self):
        tk.Frame(self.root, bg=INK_100, height=1).pack(fill="x", side="bottom")
        self._bottom = tk.Frame(self.root, bg=BG_ACTION)
        self._bottom.pack(fill="x", side="bottom")

        self._build_action_panel()
        self._build_progress_panel()
        self._build_success_panel()
        self._show_panel("action")

    def _show_panel(self, which: str):
        for name, frame in [("action",   self._action_panel),
                             ("progress", self._progress_panel),
                             ("success",  self._success_panel)]:
            if name == which:
                frame.pack(fill="x")
            else:
                frame.pack_forget()

    # Action bar
    def _build_action_panel(self):
        self._action_panel = tk.Frame(self._bottom, bg=BG_ACTION)

        row = tk.Frame(self._action_panel, bg=BG_ACTION)
        row.pack(fill="x", padx=24, pady=(12, 14))

        # Save path (left side)
        sp = tk.Frame(row, bg=BG_ACTION)
        sp.pack(side="left", fill="x", expand=True)

        # Folder icon
        fi = tk.Canvas(sp, width=30, height=30,
                       bg=BG_ACTION, highlightthickness=0)
        fi.pack(side="left", padx=(0, 8))
        fi.create_rectangle(1, 9, 29, 25, fill=BG_PANEL, outline=INK_200, width=1)
        fi.create_rectangle(1, 5, 12, 11, fill=BG_PANEL, outline=INK_200, width=1)

        sp_text = tk.Frame(sp, bg=BG_ACTION)
        sp_text.pack(side="left")

        tk.Label(sp_text, text="저장 위치",
                 bg=BG_ACTION, fg=INK_500,
                 font=(FONT, 7, "bold")).pack(anchor="w")

        path_row = tk.Frame(sp_text, bg=BG_ACTION)
        path_row.pack(anchor="w")

        self.path_lbl = tk.Label(path_row,
                                  text=self._shorten_path(self.output_dir),
                                  bg=BG_ACTION, fg=INK_900,
                                  font=(MONO, 8))
        self.path_lbl.pack(side="left")

        change_btn = tk.Label(path_row, text="  변경",
                              bg=BG_ACTION, fg=ACCENT,
                              font=(FONT, 8, "bold"), cursor="hand2")
        change_btn.pack(side="left")
        change_btn.bind("<Button-1>", lambda _e: self._change_output_dir())

        # Compress button (right)
        self.compress_btn = tk.Button(
            row,
            text="PDF 압축 시작  →",
            bg=ACCENT, fg="white",
            activebackground=ACCENT_DK, activeforeground="white",
            font=(FONT, 10, "bold"),
            relief="flat", cursor="hand2",
            padx=18, pady=8,
            command=self._start_compression,
        )
        self.compress_btn.pack(side="right")

    # Progress panel
    def _build_progress_panel(self):
        self._progress_panel = tk.Frame(self._bottom, bg=BG_ACTION)

        inner = tk.Frame(self._progress_panel, bg=BG_ACTION)
        inner.pack(fill="x", padx=24, pady=(12, 14))

        # Top row: dot + status text + percentage
        top_row = tk.Frame(inner, bg=BG_ACTION)
        top_row.pack(fill="x", pady=(0, 8))

        left = tk.Frame(top_row, bg=BG_ACTION)
        left.pack(side="left")

        self._prog_dot = tk.Canvas(left, width=6, height=6,
                                    bg=BG_ACTION, highlightthickness=0)
        self._prog_dot.pack(side="left", padx=(0, 6), pady=3)
        self._prog_dot.create_oval(0, 0, 6, 6, fill=ACCENT, outline="")

        self._status_lbl = tk.Label(left, text="준비 중...",
                                     bg=BG_ACTION, fg=INK_900,
                                     font=(FONT, 9, "bold"))
        self._status_lbl.pack(side="left")

        self._pct_lbl = tk.Label(top_row, text="0%",
                                  bg=BG_ACTION, fg=ACCENT,
                                  font=(MONO, 9, "bold"))
        self._pct_lbl.pack(side="right")

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            inner, variable=self.progress_var,
            style="Accent.Horizontal.TProgressbar",
            mode="determinate",
        )
        self.progress_bar.pack(fill="x", pady=(0, 8))

        # Sub row: file counter + ETA
        sub = tk.Frame(inner, bg=BG_ACTION)
        sub.pack(fill="x")
        self._sub_left  = tk.Label(sub, text="", bg=BG_ACTION, fg=INK_500,
                                    font=(MONO, 8))
        self._sub_left.pack(side="left")
        self._sub_right = tk.Label(sub, text="", bg=BG_ACTION, fg=INK_500,
                                    font=(MONO, 8))
        self._sub_right.pack(side="right")

    # Success panel
    def _build_success_panel(self):
        self._success_panel = tk.Frame(self._bottom, bg=SUCCESS_BG)

        inner = tk.Frame(self._success_panel, bg=SUCCESS_BG)
        inner.pack(fill="x", padx=24, pady=(12, 14))

        # Check circle
        chk = tk.Canvas(inner, width=36, height=36,
                        bg=SUCCESS_BG, highlightthickness=0)
        chk.pack(side="left", padx=(0, 14))
        chk.create_oval(0, 0, 36, 36, fill=SUCCESS, outline="")
        chk.create_line(8, 18, 15, 26, 28, 10,
                        fill="white", width=3,
                        joinstyle="round", capstyle="round")

        msg = tk.Frame(inner, bg=SUCCESS_BG)
        msg.pack(side="left", fill="x", expand=True)

        self._done_title = tk.Label(msg, text="",
                                     bg=SUCCESS_BG, fg=SUCCESS_DK,
                                     font=(FONT, 11, "bold"))
        self._done_title.pack(anchor="w")

        self._done_stats = tk.Label(msg, text="",
                                     bg=SUCCESS_BG, fg=SUCCESS_MID,
                                     font=(MONO, 8))
        self._done_stats.pack(anchor="w", pady=(2, 0))

        open_btn = tk.Button(
            inner,
            text="📁  결과 폴더 열기  →",
            bg=BG_PANEL, fg=SUCCESS_DK,
            activebackground="#eef8f1", activeforeground=SUCCESS_DK,
            font=(FONT, 9, "bold"),
            relief="groove", cursor="hand2",
            padx=12, pady=5,
            command=self._open_output_dir,
        )
        open_btn.pack(side="right")

    # ── Status rail ──────────────────────────────────────────────────────────

    def _build_status_rail(self):
        tk.Frame(self.root, bg=INK_100, height=1).pack(fill="x", side="bottom")
        rail = tk.Frame(self.root, bg=BG_TITLEBAR)
        rail.pack(fill="x", side="bottom")

        tk.Label(rail, text="● 오프라인 모드",
                 bg=BG_TITLEBAR, fg=SUCCESS,
                 font=(FONT, 7)).pack(side="left", padx=14, pady=5)

        py_ver  = f"Python {sys.version_info.major}.{sys.version_info.minor}"
        r_txt   = f"{py_ver} · PyMuPDF · pikepdf   {APP_VERSION}"
        tk.Label(rail, text=r_txt,
                 bg=BG_TITLEBAR, fg=INK_500,
                 font=(MONO, 7)).pack(side="right", padx=14, pady=5)

    # ── Event handlers ───────────────────────────────────────────────────────

    def _browse_files(self):
        if self.is_compressing:
            return
        paths = filedialog.askopenfilenames(
            title="PDF 파일 선택",
            filetypes=[("PDF 파일", "*.pdf"), ("모든 파일", "*.*")],
        )
        if paths:
            self._add_files(list(paths))

    def _on_dnd_drop(self, event):
        if self.is_compressing:
            return
        raw: str = event.data
        if "{" in raw:
            paths = re.findall(r"\{([^}]+)\}", raw)
        else:
            paths = raw.split()
        valid = [p for p in paths
                 if p.lower().endswith(".pdf") and os.path.isfile(p)]
        self._add_files(valid)
        self._draw_drop_zone(active=False)

    def _add_files(self, paths: list):
        for path in paths:
            if path in self.files or not path.lower().endswith(".pdf"):
                continue
            size = os.path.getsize(path)
            iid  = self.tree.insert("", "end",
                                    values=(os.path.basename(path),
                                            format_size(size),
                                            "—", "—"),
                                    tags=("pending",))
            self.files[path] = {"original_size": size,
                                 "compressed_size": None,
                                 "tree_id": iid}
        self._update_count_label()

    def _update_count_label(self):
        n     = len(self.files)
        total = sum(v["original_size"] for v in self.files.values())
        self.count_lbl.configure(
            text=(f"{n}개 파일  ·  총 {format_size(total)}" if n else "0개 파일"))

    def _remove_selected(self, _event=None):
        if self.is_compressing:
            return
        for iid in self.tree.selection():
            for path, info in list(self.files.items()):
                if info["tree_id"] == iid:
                    del self.files[path]
                    break
            self.tree.delete(iid)
        self._update_count_label()

    def _change_output_dir(self):
        path = filedialog.askdirectory(title="저장 위치 선택",
                                       initialdir=self.output_dir)
        if path:
            self.output_dir = path
            self.path_lbl.configure(text=self._shorten_path(path))

    def _start_compression(self):
        if self.is_compressing:
            return
        if not self.files:
            messagebox.showwarning("파일 없음", "압축할 PDF 파일을 먼저 추가하세요.")
            return

        ensure_dir(self.output_dir)
        self.is_compressing = True
        self.compress_btn.configure(state="disabled", bg=INK_300)

        for path, info in self.files.items():
            self.tree.item(info["tree_id"],
                           values=(os.path.basename(path),
                                   format_size(info["original_size"]),
                                   "—", "—"),
                           tags=("pending",))
            info["compressed_size"] = None

        self.progress_var.set(0)
        self._status_lbl.configure(text="준비 중...")
        self._pct_lbl.configure(text="0%")
        self._sub_left.configure(text="")
        self._sub_right.configure(text="")
        self._show_panel("progress")
        self._start_dot_anim()

        threading.Thread(target=self._worker, daemon=True).start()

    # ── Progress dot animation ────────────────────────────────────────────────

    def _start_dot_anim(self):
        self._dot_phase = 0
        self._animate_dot()

    def _animate_dot(self):
        if not self.is_compressing:
            return
        phase  = self._dot_phase % 20
        alpha  = phase / 10.0 if phase < 10 else (20 - phase) / 10.0
        # Interpolate between dim (#f0a99f) and bright (#e05543)
        r = int(0xf0 + (0xe0 - 0xf0) * alpha)
        g = int(0xa9 + (0x55 - 0xa9) * alpha)
        b = int(0x9f + (0x43 - 0x9f) * alpha)
        col = f"#{r:02x}{g:02x}{b:02x}"
        self._prog_dot.delete("all")
        self._prog_dot.create_oval(0, 0, 6, 6, fill=col, outline="")
        self._dot_phase += 1
        self._dot_anim_id = self.root.after(60, self._animate_dot)

    # ── Background worker ─────────────────────────────────────────────────────

    def _worker(self):
        entries     = list(self.files.items())
        total_files = len(entries)
        total_orig  = 0
        total_comp  = 0
        mode        = self.mode.get()

        for fi, (path, info) in enumerate(entries):
            fname = os.path.basename(path)

            def _ui_start(fn=fname, i=fi, n=total_files):
                self._status_lbl.configure(text=f"처리 중: {fn}")
                self._sub_left.configure(text=f"{i + 1} / {n} 파일")

            self.root.after(0, _ui_start)

            out_path = get_output_path(path, self.output_dir)

            def _make_cb(fi_=fi, n_=total_files):
                def cb(cur, tot):
                    pct = (fi_ + cur / tot) / n_ * 100
                    rem = max(0, int((100 - pct) / max(pct / max(fi_ + 1, 1), 0.1)))

                    def _upd(p=pct, r=rem):
                        self.progress_var.set(p)
                        self._pct_lbl.configure(text=f"{p:.0f}%")
                        self._sub_right.configure(text=f"예상 남은 시간: {r}초")

                    self.root.after(0, _upd)

                return cb

            try:
                in_sz, out_sz = compress_pdf(path, out_path, mode, _make_cb())
                total_orig += in_sz
                total_comp += out_sz
                ratio = (1 - out_sz / in_sz) * 100 if in_sz else 0

                def _upd_row(iid=info["tree_id"], p=path,
                             s=in_sz, o=out_sz, r=ratio):
                    self.tree.item(iid,
                                   values=(os.path.basename(p),
                                           format_size(s),
                                           format_size(o),
                                           f"−{r:.1f}%"),
                                   tags=("done",))
                    self.files[p]["compressed_size"] = o

                self.root.after(0, _upd_row)

            except Exception:
                def _err_row(iid=info["tree_id"], p=path,
                             s=info["original_size"]):
                    self.tree.item(iid,
                                   values=(os.path.basename(p),
                                           format_size(s),
                                           "오류", ""),
                                   tags=("error",))

                self.root.after(0, _err_row)

        self.root.after(0, self._on_done, total_files, total_orig, total_comp)

    def _on_done(self, n_files: int, total_orig: int, total_comp: int):
        self.is_compressing = False
        self.compress_btn.configure(state="normal", bg=ACCENT)
        self.progress_var.set(100)

        if self._dot_anim_id:
            self.root.after_cancel(self._dot_anim_id)
            self._dot_anim_id = None

        ratio = (1 - total_comp / total_orig) * 100 if total_orig else 0
        saved = total_orig - total_comp
        self._done_title.configure(text=f"{n_files}개 파일 압축 완료")
        self._done_stats.configure(
            text=(f"{format_size(total_orig)}  →  {format_size(total_comp)}"
                  f"    −{ratio:.1f}%  ({format_size(saved)} 절약)"))
        self._show_panel("success")

    def _open_output_dir(self):
        try:
            os.startfile(self.output_dir)
        except Exception:
            pass
