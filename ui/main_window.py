"""
Main application window.
All UI components live here: header, drop-zone, file list, quality selector,
action bar, and progress/result panel.
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core.utils import format_size, get_output_path, ensure_dir
from core.compressor import compress_pdf

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------
BG         = "#FAFAFA"
ACCENT     = "#E74C3C"
ACCENT_DK  = "#C0392B"
TEXT       = "#2C3E50"
SUBTEXT    = "#95A5A6"
BORDER     = "#DCDDE1"
LIST_BG    = "#FFFFFF"
LIST_HDR   = "#F5F6FA"
ACTION_BG  = "#ECEFF1"
SUCCESS    = "#27AE60"
ERROR_CLR  = "#E74C3C"

# Pick a font that renders Korean on Windows; fall back gracefully
_CANDIDATES = ["Malgun Gothic", "맑은 고딕", "Arial Unicode MS", "TkDefaultFont"]
FONT = _CANDIDATES[0]       # Malgun Gothic is always present on Win 10/11


class MainWindow:
    def __init__(self, root: tk.Tk, has_dnd: bool = False):
        self.root = root
        self.has_dnd = has_dnd
        # {path: {"original_size": int, "compressed_size": int|None, "tree_id": str}}
        self.files: dict = {}
        self.output_dir = os.path.join(os.path.expanduser("~"), "Desktop", "PDF압축결과")
        self.mode = tk.StringVar(value="recommended")
        self.is_compressing = False
        self._open_btn = None

        self._setup_window()
        self._setup_style()
        self._build_header()
        self._build_drop_zone()
        self._build_file_list()
        self._build_quality_panel()
        self._build_action_bar()
        self._build_progress_panel()

    # ------------------------------------------------------------------
    # Window / style setup
    # ------------------------------------------------------------------

    def _setup_window(self):
        self.root.title("PDF 압축기")
        self.root.geometry("680x590")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"680x590+{(sw-680)//2}+{(sh-590)//2}")

    def _setup_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure("Files.Treeview",
                        background=LIST_BG, foreground=TEXT,
                        fieldbackground=LIST_BG,
                        font=(FONT, 9), rowheight=26)
        style.configure("Files.Treeview.Heading",
                        background=LIST_HDR, foreground=TEXT,
                        font=(FONT, 9, "bold"), relief="flat")
        style.map("Files.Treeview",
                  background=[("selected", "#EEF2FF")],
                  foreground=[("selected", TEXT)])

        style.configure("Red.Horizontal.TProgressbar",
                        background=ACCENT, troughcolor="#E0E0E0", thickness=8)

        style.configure("Mode.TRadiobutton",
                        background=BG, foreground=TEXT,
                        font=(FONT, 9))
        style.map("Mode.TRadiobutton",
                  background=[("active", BG)])

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=ACCENT, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="  PDF 압축기",
                 bg=ACCENT, fg="white",
                 font=(FONT, 14, "bold")).pack(side="left", padx=12, pady=12)
        tk.Label(hdr, text="v1.0  ",
                 bg=ACCENT, fg="#FFCDD2",
                 font=(FONT, 8)).pack(side="right", padx=4)

    # ------------------------------------------------------------------
    # Drop zone
    # ------------------------------------------------------------------

    def _build_drop_zone(self):
        outer = tk.Frame(self.root, bg=BG, padx=16, pady=10)
        outer.pack(fill="x")

        self.drop_canvas = tk.Canvas(outer, width=648, height=100,
                                     bg=BG, highlightthickness=0,
                                     cursor="hand2")
        self.drop_canvas.pack()
        self._draw_drop_zone(active=False)

        self.drop_canvas.bind("<Button-1>", lambda _e: self._browse_files())
        self.drop_canvas.bind("<Enter>",    lambda _e: self._draw_drop_zone(active=True))
        self.drop_canvas.bind("<Leave>",    lambda _e: self._draw_drop_zone(active=False))

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
        c.delete("all")
        border = ACCENT if active else BORDER
        fill   = "#FFF5F5" if active else BG

        c.configure(bg=fill)
        c.create_rectangle(2, 2, 646, 98,
                           outline=border, width=2, dash=(8, 4), fill=fill)

        arrow_clr = ACCENT if active else SUBTEXT
        c.create_text(324, 36, text="▼",
                      font=(FONT, 18), fill=arrow_clr)

        if self.has_dnd:
            main_txt = "PDF 파일을 여기에 드래그하거나 클릭하여 선택"
        else:
            main_txt = "클릭하여 PDF 파일 선택 (여러 파일 가능)"

        c.create_text(324, 66, text=main_txt,
                      font=(FONT, 9),
                      fill=TEXT if active else SUBTEXT)
        c.create_text(324, 84, text="※ 원본 파일은 변경되지 않습니다",
                      font=(FONT, 8), fill=SUBTEXT)

    # ------------------------------------------------------------------
    # File list
    # ------------------------------------------------------------------

    def _build_file_list(self):
        outer = tk.Frame(self.root, bg=BG, padx=16)
        outer.pack(fill="x")

        tk.Label(outer, text="파일 목록",
                 bg=BG, fg=TEXT,
                 font=(FONT, 9, "bold")).pack(anchor="w", pady=(0, 4))

        border_frame = tk.Frame(outer, bg=BORDER, padx=1, pady=1)
        border_frame.pack(fill="x")

        inner = tk.Frame(border_frame, bg=LIST_BG)
        inner.pack(fill="both")

        cols = ("filename", "original", "compressed", "ratio")
        self.tree = ttk.Treeview(inner, columns=cols,
                                  show="headings",
                                  style="Files.Treeview",
                                  height=5)

        self.tree.heading("filename",   text="파일명")
        self.tree.heading("original",   text="원본 크기")
        self.tree.heading("compressed", text="압축 크기")
        self.tree.heading("ratio",      text="압축률")

        self.tree.column("filename",   width=336, anchor="w",      stretch=False)
        self.tree.column("original",   width=94,  anchor="center", stretch=False)
        self.tree.column("compressed", width=94,  anchor="center", stretch=False)
        self.tree.column("ratio",      width=94,  anchor="center", stretch=False)

        sb = ttk.Scrollbar(inner, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.tree.bind("<Delete>", self._remove_selected)

        hint = tk.Frame(self.root, bg=BG, padx=16)
        hint.pack(fill="x")
        tk.Label(hint, text="Delete 키로 목록에서 제거",
                 bg=BG, fg=SUBTEXT, font=(FONT, 8)).pack(anchor="e")

    # ------------------------------------------------------------------
    # Quality panel
    # ------------------------------------------------------------------

    def _build_quality_panel(self):
        outer = tk.Frame(self.root, bg=BG, padx=16, pady=6)
        outer.pack(fill="x")

        tk.Label(outer, text="압축 수준:",
                 bg=BG, fg=TEXT,
                 font=(FONT, 9, "bold")).pack(side="left", padx=(0, 14))

        options = [
            ("extreme",     "최대 압축  (파일 최소화)"),
            ("recommended", "권장  (균형)"),
            ("low",         "저압축  (화질 우선)"),
        ]
        for value, label in options:
            ttk.Radiobutton(outer, text=label,
                            variable=self.mode, value=value,
                            style="Mode.TRadiobutton").pack(side="left", padx=10)

    # ------------------------------------------------------------------
    # Action bar
    # ------------------------------------------------------------------

    def _build_action_bar(self):
        outer = tk.Frame(self.root, bg=ACTION_BG, padx=16, pady=10)
        outer.pack(fill="x")

        left = tk.Frame(outer, bg=ACTION_BG)
        left.pack(side="left", fill="x", expand=True)

        tk.Label(left, text="저장 위치:",
                 bg=ACTION_BG, fg=TEXT,
                 font=(FONT, 9)).pack(side="left")

        self.output_label = tk.Label(left,
                                      text=self._shorten_path(self.output_dir),
                                      bg=ACTION_BG, fg=ACCENT,
                                      font=(FONT, 9), cursor="hand2")
        self.output_label.pack(side="left", padx=(4, 0))
        self.output_label.bind("<Button-1>", lambda _e: self._change_output_dir())

        self.compress_btn = tk.Button(
            outer, text="PDF 압축",
            bg=ACCENT, fg="white",
            activebackground=ACCENT_DK, activeforeground="white",
            font=(FONT, 10, "bold"),
            relief="flat", cursor="hand2",
            padx=20, pady=6,
            command=self._start_compression,
        )
        self.compress_btn.pack(side="right")

    # ------------------------------------------------------------------
    # Progress / result panel
    # ------------------------------------------------------------------

    def _build_progress_panel(self):
        self.prog_frame = tk.Frame(self.root, bg=BG, padx=16, pady=8)
        self.prog_frame.pack(fill="x")

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self.prog_frame,
            variable=self.progress_var,
            style="Red.Horizontal.TProgressbar",
            mode="determinate",
            length=648,
        )

        self.status_label = tk.Label(self.prog_frame, text="",
                                      bg=BG, fg=SUBTEXT,
                                      font=(FONT, 9), anchor="w")
        self.status_label.pack(fill="x")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

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
        # tkinterdnd2 on Windows: brace-delimited for paths with spaces
        import re
        if "{" in raw:
            paths = re.findall(r"\{([^}]+)\}", raw)
        else:
            paths = raw.split()
        valid = [p for p in paths
                 if p.lower().endswith(".pdf") and os.path.isfile(p)]
        self._add_files(valid)
        self._draw_drop_zone(active=False)

    def _add_files(self, paths: list[str]):
        for path in paths:
            if path in self.files:
                continue
            if not path.lower().endswith(".pdf"):
                continue
            size = os.path.getsize(path)
            iid = self.tree.insert("", "end", values=(
                os.path.basename(path),
                format_size(size),
                "—",
                "—",
            ))
            self.files[path] = {
                "original_size": size,
                "compressed_size": None,
                "tree_id": iid,
            }

    def _remove_selected(self, _event=None):
        for iid in self.tree.selection():
            for path, info in list(self.files.items()):
                if info["tree_id"] == iid:
                    del self.files[path]
                    break
            self.tree.delete(iid)

    def _change_output_dir(self):
        path = filedialog.askdirectory(title="저장 위치 선택",
                                       initialdir=self.output_dir)
        if path:
            self.output_dir = path
            self.output_label.configure(text=self._shorten_path(path))

    def _start_compression(self):
        if self.is_compressing:
            return
        if not self.files:
            messagebox.showwarning("파일 없음", "압축할 PDF 파일을 먼저 추가하세요.")
            return

        ensure_dir(self.output_dir)
        self.is_compressing = True
        self.compress_btn.configure(state="disabled", bg="#AAAAAA")

        # Reset compressed columns
        for info in self.files.values():
            self.tree.item(info["tree_id"], values=(
                os.path.basename(next(k for k, v in self.files.items()
                                      if v is info)),
                format_size(info["original_size"]),
                "—", "—",
            ))
        # Re-set all rows properly
        for path, info in self.files.items():
            self.tree.item(info["tree_id"], values=(
                os.path.basename(path),
                format_size(info["original_size"]),
                "—", "—",
            ))
            info["compressed_size"] = None

        # Show progress bar
        if self._open_btn:
            self._open_btn.destroy()
            self._open_btn = None
        self.progress_var.set(0)
        self.progress_bar.pack(fill="x", pady=(0, 4))
        self.status_label.configure(text="준비 중...", fg=SUBTEXT)

        t = threading.Thread(target=self._worker, daemon=True)
        t.start()

    # ------------------------------------------------------------------
    # Background worker
    # ------------------------------------------------------------------

    def _worker(self):
        entries = list(self.files.items())
        total_files = len(entries)
        total_orig = 0
        total_comp = 0
        mode = self.mode.get()

        for fi, (path, info) in enumerate(entries):
            fname = os.path.basename(path)
            self.root.after(0, lambda t=fname, i=fi, n=total_files:
                            self.status_label.configure(
                                text=f"처리 중: {t}  ({i+1}/{n})", fg=SUBTEXT))

            out_path = get_output_path(path, self.output_dir)

            def _make_cb(fi, total_files):
                def cb(cur, tot):
                    pct = (fi + cur / tot) / total_files * 100
                    self.root.after(0, self.progress_var.set, pct)
                return cb

            try:
                in_sz, out_sz = compress_pdf(path, out_path, mode,
                                             _make_cb(fi, total_files))
                total_orig += in_sz
                total_comp += out_sz
                ratio = (1 - out_sz / in_sz) * 100 if in_sz else 0
                iid = info["tree_id"]
                self.root.after(0, lambda i=iid, p=path, s=in_sz, o=out_sz, r=ratio:
                                self.tree.item(i, values=(
                                    os.path.basename(p),
                                    format_size(s),
                                    format_size(o),
                                    f"-{r:.1f}%",
                                )))
                info["compressed_size"] = out_sz

            except Exception as exc:
                iid = info["tree_id"]
                self.root.after(0, lambda i=iid, p=path, s=info["original_size"]:
                                self.tree.item(i, values=(
                                    os.path.basename(p),
                                    format_size(s),
                                    "오류", "",
                                )))

        self.root.after(0, self._done, total_files, total_orig, total_comp)

    def _done(self, n_files, total_orig, total_comp):
        self.is_compressing = False
        self.compress_btn.configure(state="normal", bg=ACCENT)
        self.progress_var.set(100)

        ratio = (1 - total_comp / total_orig) * 100 if total_orig else 0
        self.status_label.configure(
            fg=SUCCESS,
            text=(f"{n_files}개 파일 완료  |  "
                  f"{format_size(total_orig)} → {format_size(total_comp)}"
                  f"  ({ratio:.1f}% 감소)"),
        )

        self._open_btn = tk.Button(
            self.prog_frame, text="결과 폴더 열기  ▸",
            bg=LIST_BG, fg=ACCENT,
            activebackground="#FFF5F5", activeforeground=ACCENT_DK,
            relief="flat", cursor="hand2",
            font=(FONT, 9, "bold"),
            padx=10, pady=3,
            command=self._open_output_dir,
        )
        self._open_btn.pack(anchor="e", pady=(4, 0))

    def _open_output_dir(self):
        try:
            os.startfile(self.output_dir)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _shorten_path(path: str, max_len: int = 44) -> str:
        return path if len(path) <= max_len else "…" + path[-(max_len - 1):]
