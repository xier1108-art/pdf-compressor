"""
Design tokens + QSS stylesheet.
Mirrors the handoff mockup's CSS 1:1 (warm beige / terracotta palette).
"""

# ── Color tokens ─────────────────────────────────────────────────────────────
BG_APP       = "#f4f1ee"
BG_WINDOW    = "#ffffff"
BG_TITLEBAR  = "#f8f8f8"
BG_HEADER_A  = "#fff6f3"
BG_HEADER_B  = "#ffffff"
BG_LIST_HDR  = "#fbf9f6"
BG_ACTION    = "#f7f4ef"
BG_SUBTLE    = "#faf8f5"
BG_PANEL     = "#ffffff"

INK_900 = "#1a1814"
INK_700 = "#3a342c"
INK_500 = "#7a7367"
INK_400 = "#9b9388"
INK_300 = "#c7bfb2"
INK_200 = "#e5ded0"
INK_100 = "#eeeae2"
INK_50  = "#f6f3ed"

ACCENT       = "#e05543"
ACCENT_DK    = "#c73a28"
ACCENT_TINT  = "#fef4f1"
ACCENT_SOFT  = "#fdece8"
ACCENT_HOVER = "#ea5d4b"

SUCCESS      = "#3f8f5e"
SUCCESS_BG   = "#f0faf3"
SUCCESS_DK   = "#1f5237"
SUCCESS_MID  = "#3d6b51"
SUCCESS_BRD  = "#d5ead9"

APP_VERSION  = "v1.6.0"
FONT_SANS    = "Pretendard, Malgun Gothic, \"맑은 고딕\", Segoe UI"
FONT_MONO    = "Consolas, \"Courier New\", monospace"


# ── Main stylesheet ─────────────────────────────────────────────────────────
QSS = f"""
* {{
    font-family: {FONT_SANS};
    outline: none;
}}

#rootWindow {{
    background: {BG_WINDOW};
}}

/* ── window frame (solid edges) ── */
#winFrame {{
    background: {BG_WINDOW};
    border: 1px solid {INK_200};
}}

/* ── titlebar ── */
#titleBar {{
    background: {BG_TITLEBAR};
    border-bottom: 1px solid {INK_100};
}}
#titleText {{
    color: {INK_700};
    font-size: 12px;
    font-weight: 500;
}}
QPushButton#tbBtn {{
    background: transparent;
    border: 0;
    color: {INK_500};
    font-size: 11px;
    min-width: 46px;
    min-height: 34px;
    max-width: 46px;
    max-height: 34px;
}}
QPushButton#tbBtn:hover {{
    background: rgba(0, 0, 0, 0.04);
    color: {INK_900};
}}
QPushButton#tbClose:hover {{
    background: #e81123;
    color: white;
}}

/* ── app header ── */
#appHeader {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                 stop:0 {BG_HEADER_A}, stop:1 {BG_HEADER_B});
    border-bottom: 1px solid {INK_100};
}}
#brandMark {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                 stop:0 {ACCENT}, stop:1 #d8402a);
    border-radius: 9px;
}}
#brandTitle {{
    color: {INK_900};
    font-size: 17px;
    font-weight: 700;
}}
#brandSubtitle {{
    color: {INK_500};
    font-size: 11px;
}}
#engineBadge {{
    background: {INK_900};
    color: #f8f4ed;
    border-radius: 999px;
    padding: 5px 12px 5px 10px;
    font-size: 11px;
    font-weight: 600;
}}
#engineBadge[fallback="true"] {{
    background: #555555;
}}
#engineVersion {{
    color: rgba(255, 255, 255, 0.55);
    font-family: {FONT_MONO};
    font-size: 10px;
    font-weight: 500;
}}

/* ── drop zone ── */
#dropZone {{
    background: {ACCENT_TINT};
    border: 2px dashed rgba(224, 85, 67, 0.45);
    border-radius: 10px;
}}
#dropZone[hover="true"] {{
    background: #fdece7;
    border: 2px dashed {ACCENT};
}}
#dropZone[dragActive="true"] {{
    background: #fde5df;
    border: 2px solid {ACCENT};
}}
#dzIcon {{
    background: white;
    border: 1px solid rgba(224, 85, 67, 0.15);
    border-radius: 22px;
    color: {ACCENT};
}}
#dzTitle {{
    color: {INK_900};
    font-size: 13px;
    font-weight: 600;
}}
#dzKbd {{
    background: white;
    border: 1px solid {INK_200};
    border-bottom: 2px solid {INK_200};
    border-radius: 4px;
    padding: 1px 7px;
    color: {INK_700};
    font-family: {FONT_MONO};
    font-size: 10px;
}}
#dzSub {{
    color: {INK_500};
    font-size: 11px;
}}

/* ── section head ── */
#sectionHead {{
    color: {INK_700};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
#sectionCount {{
    color: {INK_500};
    font-size: 11px;
}}

/* ── file list ── */
#fileListWrap {{
    background: {BG_PANEL};
    border: 1px solid {INK_100};
    border-radius: 8px;
}}
QTableWidget {{
    background: {BG_PANEL};
    border: 0;
    gridline-color: transparent;
    selection-background-color: {ACCENT_TINT};
    selection-color: {INK_900};
}}
QTableWidget::item {{
    padding: 4px 10px;
    border-bottom: 1px solid {INK_50};
    color: {INK_700};
    font-size: 12px;
}}
QTableWidget::item:selected {{
    background: {ACCENT_TINT};
    color: {INK_900};
}}
QHeaderView {{
    background: {BG_LIST_HDR};
    border: 0;
    border-bottom: 1px solid {INK_100};
}}
QHeaderView::section {{
    background: {BG_LIST_HDR};
    color: {INK_500};
    border: 0;
    padding: 8px 10px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.06em;
}}
QTableCornerButton::section {{
    background: {BG_LIST_HDR};
    border: 0;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    border: 0;
}}
QScrollBar::handle:vertical {{
    background: {INK_200};
    border-radius: 4px;
    min-height: 30px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background: {INK_300};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

#emptyState {{
    background: transparent;
    min-height: 180px;
}}
#emptyStateIcon {{
    color: {INK_300};
    font-size: 22px;
}}
#emptyStateText {{
    color: {INK_400};
    font-size: 12px;
}}

/* Ratio bar (custom widget inside cell) */
#ratioBarBg {{
    background: {INK_100};
    border-radius: 3px;
    max-height: 5px;
    min-height: 5px;
}}
#ratioBarFill {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                 stop:0 {SUCCESS}, stop:1 #5bb07e);
    border-radius: 3px;
}}
#ratioText {{
    color: {SUCCESS};
    font-family: {FONT_MONO};
    font-size: 11px;
    font-weight: 700;
}}
#ratioText[pending="true"] {{
    color: {INK_300};
    font-weight: 400;
}}
#ratioText[working="true"] {{
    color: {ACCENT};
}}

/* ── quality segmented ── */
#qualityLabel {{
    color: {INK_700};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
#qualitySeg {{
    background: {INK_50};
    border: 1px solid {INK_100};
    border-radius: 8px;
}}
#qCard {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    min-height: 64px;
}}
#qCard:hover {{
    background: rgba(255, 255, 255, 0.6);
}}
#qCard[active="true"] {{
    background: white;
    border: 1px solid {ACCENT};
}}
#qCardDot {{
    background: {INK_200};
    border-radius: 4px;
    min-width: 8px; max-width: 8px;
    min-height: 8px; max-height: 8px;
}}
#qCardDot[active="true"] {{
    background: {ACCENT};
    border: 2px solid white;
}}
#qCardName {{
    color: {INK_900};
    font-size: 12px;
    font-weight: 600;
}}
#qCardSpec {{
    color: {INK_500};
    font-family: {FONT_MONO};
    font-size: 10px;
}}
#qCardEst {{
    color: {INK_400};
    font-size: 10px;
}}
#qCardEst[active="true"] {{
    color: {INK_700};
}}
#qCardEstStrong {{
    color: {SUCCESS};
    font-family: {FONT_MONO};
    font-size: 10px;
    font-weight: 700;
}}

/* ── action bar ── */
#actionBar {{
    background: {BG_ACTION};
    border-top: 1px solid {INK_100};
}}
#spIcon {{
    background: white;
    border: 1px solid {INK_100};
    border-radius: 6px;
    color: {ACCENT};
    font-size: 13px;
}}
#spLabel {{
    color: {INK_500};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}}
#spValue {{
    color: {INK_900};
    font-family: {FONT_MONO};
    font-size: 12px;
}}
QPushButton#spChange {{
    background: transparent;
    border: 0;
    color: {ACCENT};
    font-size: 11px;
    font-weight: 600;
    padding: 0 0 0 4px;
}}
QPushButton#spChange:hover {{
    text-decoration: underline;
}}
QPushButton#btnCompress {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                 stop:0 {ACCENT_HOVER}, stop:1 {ACCENT});
    color: white;
    border: 1px solid rgba(199, 58, 40, 0.25);
    border-radius: 8px;
    padding: 10px 22px;
    font-size: 13px;
    font-weight: 700;
}}
QPushButton#btnCompress:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                 stop:0 #ef6551, stop:1 {ACCENT});
}}
QPushButton#btnCompress:pressed {{
    background: {ACCENT_DK};
}}
QPushButton#btnCompress:disabled {{
    background: {INK_200};
    color: {INK_400};
    border: 1px solid {INK_200};
}}

/* ── progress panel ── */
#progressPanel {{
    background: {BG_ACTION};
    border-top: 1px solid {INK_100};
}}
#progressDot {{
    background: {ACCENT};
    border-radius: 3px;
    min-width: 6px; max-width: 6px;
    min-height: 6px; max-height: 6px;
}}
#progressStatus {{
    color: {INK_900};
    font-size: 12px;
    font-weight: 600;
}}
#progressFile {{
    color: {INK_700};
    font-family: {FONT_MONO};
    font-size: 11px;
}}
#progressPct {{
    color: {ACCENT};
    font-family: {FONT_MONO};
    font-size: 12px;
    font-weight: 700;
}}
QProgressBar {{
    background: {INK_100};
    border: 0;
    border-radius: 3px;
    max-height: 6px;
    min-height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                 stop:0 {ACCENT}, stop:1 #ff7b5f);
    border-radius: 3px;
}}
#progressSub {{
    color: {INK_500};
    font-family: {FONT_MONO};
    font-size: 11px;
}}

/* ── success panel ── */
#successPanel {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                 stop:0 {SUCCESS_BG}, stop:1 #f7fbf8);
    border-top: 1px solid {SUCCESS_BRD};
}}
#successCheck {{
    background: {SUCCESS};
    color: white;
    border-radius: 18px;
    min-width: 36px; max-width: 36px;
    min-height: 36px; max-height: 36px;
    font-size: 18px;
    font-weight: bold;
}}
#successTitle {{
    color: {SUCCESS_DK};
    font-size: 13px;
    font-weight: 700;
}}
#successStats {{
    color: {SUCCESS_MID};
    font-family: {FONT_MONO};
    font-size: 11px;
}}
#successStatsStrong {{
    color: {SUCCESS_DK};
    font-family: {FONT_MONO};
    font-size: 11px;
    font-weight: 700;
}}
#successRatio {{
    color: {SUCCESS};
    font-family: {FONT_MONO};
    font-size: 11px;
    font-weight: 700;
}}
QPushButton#btnOpenFolder {{
    background: white;
    color: {SUCCESS_DK};
    border: 1px solid #a9d4b8;
    border-radius: 7px;
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#btnOpenFolder:hover {{
    background: #eef8f1;
    border: 1px solid #7ebe93;
}}
QPushButton#btnNewRun {{
    background: transparent;
    color: {SUCCESS_MID};
    border: 1px solid #c7e0d1;
    border-radius: 7px;
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#btnNewRun:hover {{
    background: rgba(63, 143, 94, 0.06);
    border: 1px solid #7ebe93;
    color: {SUCCESS_DK};
}}

/* ── status rail ── */
#statusRail {{
    background: {BG_TITLEBAR};
    border-top: 1px solid {INK_100};
}}
#railChip {{
    color: {INK_700};
    font-family: {FONT_MONO};
    font-size: 10px;
}}
#railDot {{
    background: {SUCCESS};
    border-radius: 2px;
    min-width: 5px; max-width: 5px;
    min-height: 5px; max-height: 5px;
}}
#railRight {{
    color: {INK_500};
    font-family: {FONT_MONO};
    font-size: 10px;
}}

QToolTip {{
    background: {INK_900};
    color: white;
    border: 0;
    padding: 4px 8px;
    border-radius: 4px;
}}
"""
