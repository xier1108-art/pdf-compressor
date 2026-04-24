"""
PDF 압축기 — PyQt6 메인 윈도우.
프레임리스 윈도우 + 커스텀 타이틀바 + mockup 디자인 1:1 구현.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import (
    QObject, QPoint, QPointF, QPropertyAnimation, QRectF, QSize, Qt, QThread,
    QTimer, pyqtProperty, pyqtSignal, pyqtSlot,
)
from PyQt6.QtGui import (
    QBrush, QColor, QDragEnterEvent, QDropEvent, QFont, QIcon, QMouseEvent,
    QPainter, QPainterPath, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QFileDialog, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QSizePolicy, QStackedLayout, QStackedWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from core.compressor import compress_pdf, find_ghostscript
from core.utils import ensure_dir, format_size, get_output_path

from ui import styles as S


# ─── Custom painted widgets ───────────────────────────────────────────────────

class BrandMark(QLabel):
    """36×36 rounded accent square with mini PDF icon."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 36)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0, 0, 36, 36)

        # Gradient accent square
        path = QPainterPath()
        path.addRoundedRect(rect, 9, 9)
        grad = QColor(S.ACCENT)
        p.fillPath(path, QBrush(grad))

        # Mini PDF doc (white rounded rect with folded corner)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("white"))
        p.drawRoundedRect(QRectF(9, 6, 14, 24), 2, 2)
        p.setBrush(QColor("#fde0db"))
        pts = QPainterPath()
        pts.moveTo(19, 6); pts.lineTo(23, 10); pts.lineTo(23, 12); pts.lineTo(19, 12)
        pts.closeSubpath()
        p.fillPath(pts, QBrush(QColor("#fde0db")))

        # PDF badge
        p.setBrush(QColor(S.ACCENT))
        p.drawRoundedRect(QRectF(8, 19, 20, 8), 1.5, 1.5)

        p.setPen(QColor("white"))
        f = QFont("Segoe UI", 6)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(8, 19, 20, 8), Qt.AlignmentFlag.AlignCenter, "PDF")
        p.end()


class PdfIcon(QLabel):
    """Small PDF file icon for list rows."""
    def __init__(self, size=18, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, int(size * 48 / 40))

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # Scale 40×48 → w×h
        sx, sy = w / 40, h / 48

        p.setPen(QPen(QColor(S.ACCENT), 1.5))
        p.setBrush(QColor("white"))
        path = QPainterPath()
        path.moveTo(4 * sx, 2 * sy)
        path.lineTo(26 * sx, 2 * sy)
        path.lineTo(36 * sx, 12 * sy)
        path.lineTo(36 * sx, 44 * sy)
        path.quadTo(36 * sx, 46 * sy, 34 * sx, 46 * sy)
        path.lineTo(4 * sx, 46 * sy)
        path.quadTo(2 * sx, 46 * sy, 2 * sx, 44 * sy)
        path.lineTo(2 * sx, 4 * sy)
        path.quadTo(2 * sx, 2 * sy, 4 * sx, 2 * sy)
        p.drawPath(path)

        # Folded corner
        p.setBrush(QColor("#fef4f1"))
        cp = QPainterPath()
        cp.moveTo(26 * sx, 2 * sy)
        cp.lineTo(26 * sx, 12 * sy)
        cp.lineTo(36 * sx, 12 * sy)
        p.drawPath(cp)

        # PDF badge
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(S.ACCENT))
        p.drawRoundedRect(QRectF(7 * sx, 26 * sy, 26 * sx, 13 * sy), 2, 2)

        p.setPen(QColor("white"))
        f = QFont("Segoe UI", max(5, int(self._size * 0.35)))
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(7 * sx, 26 * sy, 26 * sx, 13 * sy),
                   Qt.AlignmentFlag.AlignCenter, "PDF")
        p.end()


class PlusCircle(QLabel):
    """44×44 white circle with + sign (drop zone icon)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 44)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Circle
        p.setPen(QPen(QColor(224, 85, 67, 40), 1))
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(1, 1, 42, 42))
        # + sign
        p.setPen(QPen(QColor(S.ACCENT), 2.3, cap=Qt.PenCapStyle.RoundCap))
        p.drawLine(22, 14, 22, 30)
        p.drawLine(14, 22, 30, 22)
        p.end()


class PulsingDot(QLabel):
    """6×6 dot that pulses the accent color."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(6, 6)
        self._alpha = 1.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._phase = 0

    def start(self):
        self._phase = 0
        self._timer.start(60)

    def stop(self):
        self._timer.stop()
        self.update()

    def _tick(self):
        self._phase = (self._phase + 1) % 20
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._timer.isActive():
            t = self._phase / 10.0 if self._phase < 10 else (20 - self._phase) / 10.0
        else:
            t = 1.0
        r = int(0xf0 + (0xe0 - 0xf0) * t)
        g = int(0xa9 + (0x55 - 0xa9) * t)
        b = int(0x9f + (0x43 - 0x9f) * t)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(r, g, b))
        p.drawEllipse(QRectF(0, 0, 6, 6))
        p.end()


class CheckIcon(QLabel):
    """36×36 green filled circle with white check."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 36)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(S.SUCCESS))
        p.drawEllipse(QRectF(0, 0, 36, 36))

        pen = QPen(QColor("white"), 3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        path = QPainterPath()
        path.moveTo(10, 18)
        path.lineTo(16, 24)
        path.lineTo(27, 12)
        p.drawPath(path)
        p.end()


class RatioBar(QWidget):
    """Ratio bar + text (for file list cells)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(8)
        lay.addStretch(1)

        self.bar_bg = QFrame()
        self.bar_bg.setObjectName("ratioBarBg")
        self.bar_bg.setFixedSize(42, 5)
        bar_lay = QHBoxLayout(self.bar_bg)
        bar_lay.setContentsMargins(0, 0, 0, 0)
        bar_lay.setSpacing(0)
        self.bar_fill = QFrame()
        self.bar_fill.setObjectName("ratioBarFill")
        bar_lay.addWidget(self.bar_fill)
        bar_lay.addStretch(1)

        self.text = QLabel("—")
        self.text.setObjectName("ratioText")
        self.text.setMinimumWidth(52)
        self.text.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        lay.addWidget(self.bar_bg)
        lay.addWidget(self.text)

        self.set_pending()

    def set_pending(self):
        self.bar_bg.hide()
        self.text.setText("—")
        self.text.setProperty("pending", "true")
        self.text.setProperty("working", "false")
        self._refresh_style()

    def set_working(self):
        self.bar_bg.hide()
        self.text.setText("처리 중")
        self.text.setProperty("pending", "false")
        self.text.setProperty("working", "true")
        self._refresh_style()

    def set_done(self, ratio: float):
        self.bar_bg.show()
        w_total = 42
        fill_w = max(1, int(min(100, max(0, ratio)) / 100 * w_total))
        self.bar_fill.setFixedWidth(fill_w)
        self.text.setText(f"−{ratio:.1f}%")
        self.text.setProperty("pending", "false")
        self.text.setProperty("working", "false")
        self._refresh_style()

    def set_error(self):
        self.bar_bg.hide()
        self.text.setText("오류")
        self.text.setProperty("pending", "true")
        self.text.setProperty("working", "false")
        self._refresh_style()

    def _refresh_style(self):
        self.text.style().unpolish(self.text)
        self.text.style().polish(self.text)


class FileNameCell(QWidget):
    """PDF icon + file name label for the file column."""
    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(10)
        self.icon = PdfIcon(size=18)
        self.label = QLabel(name)
        self.label.setStyleSheet(f"color: {S.INK_900}; font-size: 12px; font-weight: 500;")
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        lay.addWidget(self.icon)
        lay.addWidget(self.label, 1)


class DropZone(QFrame):
    """Drag-drop area with dashed border."""
    filesDropped = pyqtSignal(list)
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(108)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(4)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon = PlusCircle()
        self.icon.setObjectName("dzIcon")
        lay.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignHCenter)

        title = QLabel(
            "PDF 파일을 드래그하거나 "
            "<span style='background:white; border:1px solid #e5ded0; "
            "border-radius:4px; padding:1px 6px; color:#3a342c; "
            "font-family:Consolas, monospace; font-size:10px;'>클릭</span>"
            " 하여 선택"
        )
        title.setObjectName("dzTitle")
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title, 0, Qt.AlignmentFlag.AlignHCenter)

        self.sub = QLabel("🔒 원본 파일은 변경되지 않습니다 · 여러 파일 선택 가능")
        self.sub.setObjectName("dzSub")
        lay.addWidget(self.sub, 0, Qt.AlignmentFlag.AlignHCenter)

    def enterEvent(self, _ev):
        self.setProperty("hover", "true")
        self._refresh()

    def leaveEvent(self, _ev):
        self.setProperty("hover", "false")
        self._refresh()

    def mousePressEvent(self, ev: QMouseEvent):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def dragEnterEvent(self, ev: QDragEnterEvent):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()
            self.setProperty("dragActive", "true")
            self._refresh()

    def dragLeaveEvent(self, _ev):
        self.setProperty("dragActive", "false")
        self._refresh()

    def dropEvent(self, ev: QDropEvent):
        self.setProperty("dragActive", "false")
        self._refresh()
        paths = []
        for url in ev.mimeData().urls():
            p = url.toLocalFile()
            if p.lower().endswith(".pdf") and os.path.isfile(p):
                paths.append(p)
        if paths:
            self.filesDropped.emit(paths)

    def _refresh(self):
        self.style().unpolish(self)
        self.style().polish(self)


# ─── Quality card (segmented button) ─────────────────────────────────────────

class QualityCard(QFrame):
    clicked = pyqtSignal()

    @dataclass
    class Spec:
        qid: str
        name: str
        spec: str
        est: str

    def __init__(self, spec: Spec, parent=None):
        super().__init__(parent)
        self.spec = spec
        self.setObjectName("qCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 9)
        lay.setSpacing(3)

        top = QHBoxLayout(); top.setSpacing(6); top.setContentsMargins(0, 0, 0, 0)
        self.dot = QFrame(); self.dot.setObjectName("qCardDot")
        self.dot.setFixedSize(8, 8)
        self.name_lbl = QLabel(spec.name); self.name_lbl.setObjectName("qCardName")
        top.addWidget(self.dot); top.addWidget(self.name_lbl); top.addStretch(1)

        wrap_top = QWidget(); wrap_top.setLayout(top)
        lay.addWidget(wrap_top)

        self.spec_lbl = QLabel(spec.spec); self.spec_lbl.setObjectName("qCardSpec")
        lay.addWidget(self.spec_lbl)

        est_row = QHBoxLayout(); est_row.setSpacing(4); est_row.setContentsMargins(0, 2, 0, 0)
        est_prefix = QLabel("예상 감소"); est_prefix.setObjectName("qCardEst")
        est_value  = QLabel(spec.est);   est_value.setObjectName("qCardEstStrong")
        est_row.addWidget(est_prefix); est_row.addWidget(est_value); est_row.addStretch(1)
        wrap_est = QWidget(); wrap_est.setLayout(est_row)
        lay.addWidget(wrap_est)

        self.est_prefix = est_prefix

    def mousePressEvent(self, ev: QMouseEvent):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def setActive(self, active: bool):
        self.setProperty("active", "true" if active else "false")
        self.dot.setProperty("active", "true" if active else "false")
        self.est_prefix.setProperty("active", "true" if active else "false")
        for w in (self, self.dot, self.est_prefix):
            w.style().unpolish(w); w.style().polish(w)


# ─── Compression worker (QThread) ────────────────────────────────────────────

class CompressionWorker(QThread):
    fileStarted  = pyqtSignal(int, str)            # idx, filename
    fileProgress = pyqtSignal(int, float)          # idx, overall_pct
    fileDone     = pyqtSignal(int, int, int, float) # idx, in_sz, out_sz, ratio
    fileError    = pyqtSignal(int, str)            # idx, msg
    allDone      = pyqtSignal(int, int, int)       # n_files, tot_orig, tot_comp

    def __init__(self, entries, mode: str, output_dir: str):
        super().__init__()
        self.entries = entries              # list of (idx, path)
        self.mode = mode
        self.output_dir = output_dir

    def run(self):
        total = len(self.entries)
        tot_orig = 0
        tot_comp = 0

        for fi, (idx, path) in enumerate(self.entries):
            fname = os.path.basename(path)
            self.fileStarted.emit(idx, fname)

            out_path = get_output_path(path, self.output_dir)

            def _cb(cur, tot, fi=fi):
                pct = (fi + cur / max(tot, 1)) / total * 100
                self.fileProgress.emit(idx, pct)

            try:
                in_sz, out_sz = compress_pdf(path, out_path, self.mode, _cb)
                tot_orig += in_sz
                tot_comp += out_sz
                ratio = (1 - out_sz / in_sz) * 100 if in_sz else 0
                self.fileDone.emit(idx, in_sz, out_sz, ratio)
            except Exception as exc:
                self.fileError.emit(idx, str(exc))

            self.fileProgress.emit(idx, (fi + 1) / total * 100)

        self.allDone.emit(total, tot_orig, tot_comp)


# ─── Main window ─────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setObjectName("rootWindow")
        self.setWindowTitle("PDF 압축기")
        self.resize(820, 720)

        # Frameless (no translucent background — solid edges)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)

        self.files: list[dict] = []                 # [{path, size, comp_size, widgets}, ...]
        self.output_dir = os.path.join(
            os.path.expanduser("~"), "Desktop", "PDF압축결과")
        self.current_mode = "recommended"
        self.is_compressing = False
        self._worker: Optional[CompressionWorker] = None
        self._drag_pos: Optional[QPoint] = None

        gs = find_ghostscript()
        self._has_gs = bool(gs)
        self._gs_ver = self._detect_gs_ver(gs) if gs else None

        self._build_ui()
        self.setStyleSheet(S.QSS)

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
    def _shorten_path(p: str, max_len: int = 50) -> str:
        return p if len(p) <= max_len else "…" + p[-(max_len - 1):]

    # ── UI build ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.frame = QFrame()
        self.frame.setObjectName("winFrame")
        self.setCentralWidget(self.frame)

        lay = QVBoxLayout(self.frame)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        lay.addWidget(self._build_titlebar())
        lay.addWidget(self._build_app_header())
        lay.addWidget(self._build_main(), 1)
        lay.addWidget(self._build_bottom_stack())
        lay.addWidget(self._build_status_rail())

        self._update_count()   # set initial empty-state + disable compress btn

    # Titlebar
    def _build_titlebar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("titleBar")
        bar.setFixedHeight(34)
        self._titlebar = bar

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 0, 0, 0)
        lay.setSpacing(8)

        # Mini PDF icon
        ic = QLabel()
        ic.setFixedSize(14, 14)
        pix = QPixmap(14, 14); pix.fill(Qt.GlobalColor.transparent)
        pn = QPainter(pix); pn.setRenderHint(QPainter.RenderHint.Antialiasing)
        pn.setPen(Qt.PenStyle.NoPen); pn.setBrush(QColor(S.ACCENT))
        pn.drawRoundedRect(QRectF(0, 0, 10, 14), 1, 1)
        pn.setPen(QColor("white")); pn.setFont(QFont("Segoe UI", 4, QFont.Weight.Bold))
        pn.drawText(QRectF(0, 4, 10, 8), Qt.AlignmentFlag.AlignCenter, "PDF")
        pn.end()
        ic.setPixmap(pix)
        lay.addWidget(ic)

        title = QLabel("PDF 압축기"); title.setObjectName("titleText")
        lay.addWidget(title)
        lay.addStretch(1)

        for sym, is_close, cmd in [("─", False, self.showMinimized),
                                      ("□", False, self._toggle_max),
                                      ("✕", True,  self.close)]:
            b = QPushButton(sym)
            b.setObjectName("tbClose" if is_close else "tbBtn")
            b.setFlat(True)
            b.clicked.connect(cmd)
            lay.addWidget(b)

        # tbClose falls back to tbBtn styling; add specific close styling via stylesheet
        bar.mouseDoubleClickEvent = lambda e: self._toggle_max()
        return bar

    def _toggle_max(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # App header
    def _build_app_header(self) -> QWidget:
        hdr = QFrame()
        hdr.setObjectName("appHeader")

        lay = QHBoxLayout(hdr)
        lay.setContentsMargins(24, 18, 24, 16)
        lay.setSpacing(12)

        mark = BrandMark()
        lay.addWidget(mark)

        tf = QVBoxLayout(); tf.setSpacing(2); tf.setContentsMargins(0, 0, 0, 0)
        t1 = QLabel("PDF 압축기");            t1.setObjectName("brandTitle")
        t2 = QLabel("오프라인 · 원본 보존 · 배치 처리"); t2.setObjectName("brandSubtitle")
        tf.addWidget(t1); tf.addWidget(t2)
        wrap = QWidget(); wrap.setLayout(tf)
        lay.addWidget(wrap)
        lay.addStretch(1)
        return hdr

    # Main content area (drop zone + file list + quality)
    def _build_main(self) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(18)

        # Drop zone
        self.dropzone = DropZone()
        self.dropzone.clicked.connect(self._browse_files)
        self.dropzone.filesDropped.connect(self._add_files)
        lay.addWidget(self.dropzone)

        # File list section
        file_section = QVBoxLayout(); file_section.setSpacing(8); file_section.setContentsMargins(0, 0, 0, 0)

        sh = QHBoxLayout(); sh.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("파일 목록"); lbl.setObjectName("sectionHead")
        self.count_lbl = QLabel("0개 파일"); self.count_lbl.setObjectName("sectionCount")
        sh.addWidget(lbl); sh.addStretch(1); sh.addWidget(self.count_lbl)
        sh_w = QWidget(); sh_w.setLayout(sh)
        file_section.addWidget(sh_w)

        # File list wrap — table and empty_state share the same space (QStackedLayout)
        list_wrap = QFrame(); list_wrap.setObjectName("fileListWrap")
        list_wrap.setMinimumHeight(220)
        list_stack = QStackedLayout(list_wrap)
        list_stack.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["파일명", "원본 크기", "압축 크기", "압축률", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setShowGrid(False)
        self.table.setFrameShape(QFrame.Shape.NoFrame)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setMinimumHeight(200)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 110)
        self.table.setColumnWidth(4, 28)
        self.table.setHorizontalHeaderItem(1, QTableWidgetItem("원본 크기"))
        self.table.setHorizontalHeaderItem(2, QTableWidgetItem("압축 크기"))
        self.table.setHorizontalHeaderItem(3, QTableWidgetItem("압축률"))
        for i in (1, 2, 3):
            self.table.horizontalHeaderItem(i).setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        # Empty-state overlay (shown when no files)
        self.empty_state = QFrame(); self.empty_state.setObjectName("emptyState")
        es_lay = QVBoxLayout(self.empty_state)
        es_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        es_lay.setSpacing(10)
        es_icon = QLabel("⋮⋮"); es_icon.setObjectName("emptyStateIcon")
        es_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        es_txt = QLabel("위에 PDF 파일을 드래그해서 시작하세요")
        es_txt.setObjectName("emptyStateText")
        es_txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        es_lay.addWidget(es_icon); es_lay.addWidget(es_txt)

        # Stack: empty_state (index 0) under table (index 1), same geometry
        list_stack.addWidget(self.empty_state)
        list_stack.addWidget(self.table)
        self._list_stack = list_stack
        list_stack.setCurrentIndex(0)  # start with empty state

        file_section.addWidget(list_wrap)
        fs_w = QWidget(); fs_w.setLayout(file_section)
        lay.addWidget(fs_w, 1)

        # Quality panel
        q_row = QHBoxLayout(); q_row.setSpacing(14); q_row.setContentsMargins(0, 0, 0, 0)
        q_lbl = QLabel("압축 수준"); q_lbl.setObjectName("qualityLabel")
        q_row.addWidget(q_lbl)

        q_seg = QFrame(); q_seg.setObjectName("qualitySeg")
        q_seg_lay = QHBoxLayout(q_seg); q_seg_lay.setContentsMargins(4, 4, 4, 4); q_seg_lay.setSpacing(6)
        self._q_cards = {}
        specs = [
            QualityCard.Spec("extreme",     "최대 압축", "900px · Q35",  "70–90%"),
            QualityCard.Spec("recommended", "권장",      "1600px · Q65", "40–70%"),
            QualityCard.Spec("low",         "저압축",    "2400px · Q85", "20–40%"),
        ]
        for sp in specs:
            card = QualityCard(sp)
            card.clicked.connect(lambda _=False, q=sp.qid: self._set_quality(q))
            q_seg_lay.addWidget(card, 1)
            self._q_cards[sp.qid] = card

        q_row.addWidget(q_seg, 1)
        qw = QWidget(); qw.setLayout(q_row)
        lay.addWidget(qw)

        self._set_quality(self.current_mode)

        # Table row deletion
        self.table.keyPressEvent = self._table_keypress
        return wrap

    def _table_keypress(self, ev):
        if ev.key() == Qt.Key.Key_Delete and not self.is_compressing:
            self._remove_selected_rows()
        else:
            QTableWidget.keyPressEvent(self.table, ev)

    # Bottom stack (action/progress/success)
    def _build_bottom_stack(self) -> QWidget:
        self.bottom_stack = QStackedWidget()

        # Action panel
        self.action_panel = QFrame(); self.action_panel.setObjectName("actionBar")
        ab = QHBoxLayout(self.action_panel); ab.setContentsMargins(24, 16, 24, 16); ab.setSpacing(16)

        sp_row = QHBoxLayout(); sp_row.setSpacing(10); sp_row.setContentsMargins(0, 0, 0, 0)
        sp_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        sp_icon = QLabel("📁"); sp_icon.setObjectName("spIcon")
        sp_icon.setFixedSize(26, 26); sp_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sp_row.addWidget(sp_icon, 0, Qt.AlignmentFlag.AlignVCenter)

        sp_txt_lay = QVBoxLayout(); sp_txt_lay.setSpacing(1); sp_txt_lay.setContentsMargins(0, 0, 0, 0)
        sp_txt_lay.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        sp_lbl = QLabel("저장 위치"); sp_lbl.setObjectName("spLabel")
        sp_val_row = QHBoxLayout(); sp_val_row.setSpacing(6); sp_val_row.setContentsMargins(0, 0, 0, 0)
        self.path_lbl = QLabel(self._shorten_path(self.output_dir)); self.path_lbl.setObjectName("spValue")
        change_btn = QPushButton("변경"); change_btn.setObjectName("spChange")
        change_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        change_btn.clicked.connect(self._change_output_dir)
        sp_val_row.addWidget(self.path_lbl); sp_val_row.addWidget(change_btn); sp_val_row.addStretch(1)
        sp_val_w = QWidget(); sp_val_w.setLayout(sp_val_row)
        sp_txt_lay.addWidget(sp_lbl); sp_txt_lay.addWidget(sp_val_w)
        sp_txt_w = QWidget(); sp_txt_w.setLayout(sp_txt_lay)
        sp_row.addWidget(sp_txt_w, 1)

        sp_w = QWidget(); sp_w.setLayout(sp_row)
        sp_w.setMaximumWidth(520)
        ab.addWidget(sp_w, 1)

        self.compress_btn = QPushButton("PDF 압축 시작  →")
        self.compress_btn.setObjectName("btnCompress")
        self.compress_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.compress_btn.clicked.connect(self._start_compression)
        ab.addWidget(self.compress_btn)

        # Progress panel
        self.progress_panel = QFrame(); self.progress_panel.setObjectName("progressPanel")
        pp = QVBoxLayout(self.progress_panel); pp.setContentsMargins(24, 14, 24, 18); pp.setSpacing(10)

        pp_top = QHBoxLayout(); pp_top.setSpacing(8)
        self.pulse_dot = PulsingDot()
        pp_top.addWidget(self.pulse_dot)
        self.pp_status = QLabel("준비 중..."); self.pp_status.setObjectName("progressStatus")
        pp_top.addWidget(self.pp_status)
        self.pp_file = QLabel(""); self.pp_file.setObjectName("progressFile")
        pp_top.addWidget(self.pp_file, 1)
        self.pp_pct = QLabel("0%"); self.pp_pct.setObjectName("progressPct")
        pp_top.addWidget(self.pp_pct)
        pp_top_w = QWidget(); pp_top_w.setLayout(pp_top)
        pp.addWidget(pp_top_w)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        pp.addWidget(self.progress_bar)

        pp_sub = QHBoxLayout()
        self.pp_sub_left = QLabel(""); self.pp_sub_left.setObjectName("progressSub")
        self.pp_sub_right = QLabel(""); self.pp_sub_right.setObjectName("progressSub")
        pp_sub.addWidget(self.pp_sub_left); pp_sub.addStretch(1); pp_sub.addWidget(self.pp_sub_right)
        pp_sub_w = QWidget(); pp_sub_w.setLayout(pp_sub)
        pp.addWidget(pp_sub_w)

        # Success panel
        self.success_panel = QFrame(); self.success_panel.setObjectName("successPanel")
        sp = QHBoxLayout(self.success_panel); sp.setContentsMargins(32, 16, 32, 18); sp.setSpacing(16)
        self.success_check = CheckIcon()
        sp.addWidget(self.success_check)
        sp_msg_lay = QVBoxLayout(); sp_msg_lay.setSpacing(2); sp_msg_lay.setContentsMargins(0, 0, 0, 0)
        self.success_title = QLabel(""); self.success_title.setObjectName("successTitle")
        self.success_stats = QLabel(""); self.success_stats.setObjectName("successStats")
        self.success_stats.setTextFormat(Qt.TextFormat.RichText)
        sp_msg_lay.addWidget(self.success_title); sp_msg_lay.addWidget(self.success_stats)
        sp_msg_w = QWidget(); sp_msg_w.setLayout(sp_msg_lay)
        sp.addWidget(sp_msg_w, 1)
        new_btn = QPushButton("＋  새 압축"); new_btn.setObjectName("btnNewRun")
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self._start_new_run)
        sp.addWidget(new_btn)
        open_btn = QPushButton("📁  결과 폴더 열기  →"); open_btn.setObjectName("btnOpenFolder")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(self._open_output_dir)
        sp.addWidget(open_btn)

        self.bottom_stack.addWidget(self.action_panel)
        self.bottom_stack.addWidget(self.progress_panel)
        self.bottom_stack.addWidget(self.success_panel)

        # Only the currently visible panel contributes to height — others ignored
        for p in (self.action_panel, self.progress_panel, self.success_panel):
            p.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.action_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        def _on_stack_changed(idx):
            for i in range(self.bottom_stack.count()):
                w = self.bottom_stack.widget(i)
                w.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Preferred if i == idx else QSizePolicy.Policy.Ignored,
                )
                w.adjustSize()
            self.bottom_stack.adjustSize()

        self.bottom_stack.currentChanged.connect(_on_stack_changed)
        self.bottom_stack.setCurrentWidget(self.action_panel)
        return self.bottom_stack

    # Status rail
    def _build_status_rail(self) -> QWidget:
        rail = QFrame(); rail.setObjectName("statusRail"); rail.setFixedHeight(28)
        lay = QHBoxLayout(rail); lay.setContentsMargins(16, 6, 16, 6); lay.setSpacing(6)

        dot = QFrame(); dot.setObjectName("railDot")
        lay.addWidget(dot)
        chip = QLabel("오프라인 모드"); chip.setObjectName("railChip")
        lay.addWidget(chip)
        lay.addStretch(1)

        py_ver = f"Python {sys.version_info.major}.{sys.version_info.minor}"
        right = QLabel(f"{py_ver} · PyMuPDF · pikepdf        {S.APP_VERSION}")
        right.setObjectName("railRight")
        lay.addWidget(right)
        return rail

    # ── Frameless window drag ────────────────────────────────────────────────

    def mousePressEvent(self, ev: QMouseEvent):
        if ev.button() == Qt.MouseButton.LeftButton and self._is_in_titlebar(ev.pos()):
            self._drag_pos = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            ev.accept()

    def mouseMoveEvent(self, ev: QMouseEvent):
        if self._drag_pos is not None and ev.buttons() & Qt.MouseButton.LeftButton:
            self.move(ev.globalPosition().toPoint() - self._drag_pos)
            ev.accept()

    def mouseReleaseEvent(self, _ev):
        self._drag_pos = None

    def _is_in_titlebar(self, pos: QPoint) -> bool:
        if not hasattr(self, "_titlebar"):
            return False
        tb_rect = self._titlebar.rect()
        tb_global = self._titlebar.mapTo(self, tb_rect.topLeft())
        return (tb_global.y() <= pos.y() <= tb_global.y() + tb_rect.height()
                and pos.x() < self._titlebar.width() - 3 * 46)

    # ── File management ──────────────────────────────────────────────────────

    def _browse_files(self):
        if self.is_compressing:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "PDF 파일 선택", "",
            "PDF 파일 (*.pdf);;모든 파일 (*.*)")
        if paths:
            self._add_files(paths)

    @pyqtSlot(list)
    def _add_files(self, paths: list[str]):
        existing = {f["path"] for f in self.files}
        for path in paths:
            if path in existing or not path.lower().endswith(".pdf"):
                continue
            size = os.path.getsize(path)
            row = self.table.rowCount()
            self.table.insertRow(row)

            name_cell = FileNameCell(os.path.basename(path))
            self.table.setCellWidget(row, 0, name_cell)

            orig_item = QTableWidgetItem(format_size(size))
            orig_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            orig_item.setForeground(QBrush(QColor(S.INK_700)))
            f = orig_item.font(); f.setFamily("Consolas"); f.setPointSize(9); orig_item.setFont(f)
            self.table.setItem(row, 1, orig_item)

            comp_item = QTableWidgetItem("—")
            comp_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            comp_item.setForeground(QBrush(QColor(S.INK_300)))
            comp_item.setFont(f)
            self.table.setItem(row, 2, comp_item)

            ratio = RatioBar()
            self.table.setCellWidget(row, 3, ratio)

            remove = QPushButton("✕")
            remove.setFlat(True)
            remove.setStyleSheet(f"color: {S.INK_400}; border: 0; background: transparent;"
                                  f"font-size: 11px;")
            remove.setCursor(Qt.CursorShape.PointingHandCursor)
            remove.clicked.connect(lambda _=False, p=path: self._remove_by_path(p))
            self.table.setCellWidget(row, 4, remove)

            self.files.append({
                "path": path,
                "size": size,
                "comp_size": None,
                "row": row,
                "ratio_widget": ratio,
                "comp_item": comp_item,
            })
        self._update_count()

    def _remove_by_path(self, path: str):
        if self.is_compressing:
            return
        for i, f in enumerate(self.files):
            if f["path"] == path:
                self.table.removeRow(f["row"])
                del self.files[i]
                break
        self._reindex_rows()
        self._update_count()

    def _remove_selected_rows(self):
        sel_rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in sel_rows:
            for i, f in enumerate(self.files):
                if f["row"] == r:
                    self.table.removeRow(r)
                    del self.files[i]
                    break
        self._reindex_rows()
        self._update_count()

    def _reindex_rows(self):
        for i, f in enumerate(self.files):
            f["row"] = i

    def _update_count(self):
        n = len(self.files)
        if n == 0:
            self.count_lbl.setText("0개 파일")
        else:
            total = sum(f["size"] for f in self.files)
            self.count_lbl.setText(f"{n}개 파일  ·  총 {format_size(total)}")
        # Toggle empty state vs table via stacked layout (fixed box size)
        self._list_stack.setCurrentIndex(0 if n == 0 else 1)
        # Enable compress button only when there are files and not compressing
        if hasattr(self, "compress_btn"):
            self.compress_btn.setEnabled(n > 0 and not self.is_compressing)

    def _change_output_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "저장 위치 선택", self.output_dir)
        if path:
            self.output_dir = path
            self.path_lbl.setText(self._shorten_path(path))

    # ── Quality ──────────────────────────────────────────────────────────────

    def _set_quality(self, qid: str):
        self.current_mode = qid
        for k, card in self._q_cards.items():
            card.setActive(k == qid)

    # ── Compression lifecycle ────────────────────────────────────────────────

    def _start_compression(self):
        if self.is_compressing:
            return
        if not self.files:
            QMessageBox.warning(self, "파일 없음", "압축할 PDF 파일을 먼저 추가하세요.")
            return

        ensure_dir(self.output_dir)
        self.is_compressing = True
        self.compress_btn.setDisabled(True)

        # Reset state
        for f in self.files:
            f["ratio_widget"].set_pending()
            f["comp_item"].setText("—")
            f["comp_item"].setForeground(QBrush(QColor(S.INK_300)))
            f["comp_size"] = None

        self.progress_bar.setValue(0)
        self.pp_status.setText("준비 중...")
        self.pp_file.setText("")
        self.pp_pct.setText("0%")
        self.pp_sub_left.setText("")
        self.pp_sub_right.setText("")
        self.bottom_stack.setCurrentWidget(self.progress_panel)
        self.pulse_dot.start()

        entries = [(f["row"], f["path"]) for f in self.files]
        self._worker = CompressionWorker(entries, self.current_mode, self.output_dir)
        self._worker.fileStarted.connect(self._on_file_started)
        self._worker.fileProgress.connect(self._on_file_progress)
        self._worker.fileDone.connect(self._on_file_done)
        self._worker.fileError.connect(self._on_file_error)
        self._worker.allDone.connect(self._on_all_done)
        self._worker.start()

    @pyqtSlot(int, str)
    def _on_file_started(self, idx: int, fname: str):
        self.pp_status.setText("처리 중:")
        self.pp_file.setText(fname)
        for f in self.files:
            if f["row"] == idx:
                f["ratio_widget"].set_working()
                break
        total = len(self.files)
        done_n = sum(1 for f in self.files if f["comp_size"] is not None) + 1
        self.pp_sub_left.setText(f"{done_n} / {total} 파일")

    @pyqtSlot(int, float)
    def _on_file_progress(self, _idx: int, pct: float):
        self.progress_bar.setValue(int(pct))
        self.pp_pct.setText(f"{pct:.0f}%")
        remaining = max(0, int((100 - pct) / max(pct / 5, 1)))
        self.pp_sub_right.setText(f"예상 남은 시간: {remaining}초")

    @pyqtSlot(int, int, int, float)
    def _on_file_done(self, idx: int, in_sz: int, out_sz: int, ratio: float):
        for f in self.files:
            if f["row"] == idx:
                f["comp_size"] = out_sz
                f["comp_item"].setText(format_size(out_sz))
                f["comp_item"].setForeground(QBrush(QColor(S.INK_900)))
                fnt = f["comp_item"].font(); fnt.setBold(True); f["comp_item"].setFont(fnt)
                f["ratio_widget"].set_done(ratio)
                break

    @pyqtSlot(int, str)
    def _on_file_error(self, idx: int, _msg: str):
        for f in self.files:
            if f["row"] == idx:
                f["comp_item"].setText("오류")
                f["comp_item"].setForeground(QBrush(QColor(S.ACCENT)))
                f["ratio_widget"].set_error()
                break

    @pyqtSlot(int, int, int)
    def _on_all_done(self, n_files: int, tot_orig: int, tot_comp: int):
        self.is_compressing = False
        self.compress_btn.setDisabled(False)
        self.pulse_dot.stop()

        ratio = (1 - tot_comp / tot_orig) * 100 if tot_orig else 0
        saved = tot_orig - tot_comp
        self.success_title.setText(f"{n_files}개 파일 압축 완료")
        self.success_stats.setText(
            f"<span id='successStatsStrong' style='color:{S.SUCCESS_DK};font-weight:700'>"
            f"{format_size(tot_orig)}</span>"
            f" <span style='color:{S.INK_400}'>→</span> "
            f"<span style='color:{S.SUCCESS_DK};font-weight:700'>{format_size(tot_comp)}</span>"
            f"     <span style='color:{S.SUCCESS};font-weight:700'>−{ratio:.1f}% "
            f"({format_size(saved)} 절약)</span>"
        )
        self.bottom_stack.setCurrentWidget(self.success_panel)

    def _open_output_dir(self):
        try:
            os.startfile(self.output_dir)
        except Exception:
            pass

    def _start_new_run(self):
        """Reset UI to action panel so user can add/compress new files."""
        # Clear previously compressed files from the list
        self.table.setRowCount(0)
        self.files.clear()
        self._update_count()
        self.bottom_stack.setCurrentWidget(self.action_panel)
