# PyQt6 UI 디자인 시스템 인수인계

PDF 압축기(v1.7.0) UI를 다른 압축 앱(예: 사진 압축기)에 그대로 이식하기 위한 가이드.
복붙 가능한 자산 + 구조 설명 + 적용 체크리스트.

---

## 0. TL;DR — 10분 안에 똑같은 앱 만들기

```
새 프로젝트/
├── app.py              ← QApplication entry point (복붙)
├── ui/
│   ├── styles.py       ← 색/폰트 토큰 + 전체 QSS (그대로 복붙)
│   └── main_window.py  ← 창 골격 (구조 복붙 후 이름/아이콘/작업 내용만 치환)
├── core/
│   └── compressor.py   ← 여기만 도메인 맞게 새로 작성
└── requirements.txt
```

1. `ui/styles.py` 를 **그대로** 복사 — 색/폰트/QSS 전부 재사용
2. `ui/main_window.py` 를 복사 후 **6군데만 치환** (§8 체크리스트)
3. `core/compressor.py` 만 사진 압축 로직으로 새로 작성
4. 끝

---

## 1. 디자인 시스템 토큰

### 컬러 팔레트 (warm beige / terracotta)

| 역할 | 토큰 | HEX | 용도 |
|------|------|-----|------|
| App background | `BG_APP` | `#f4f1ee` | 바탕 |
| Window | `BG_WINDOW` | `#ffffff` | 창 내부 |
| Titlebar / StatusRail | `BG_TITLEBAR` | `#f8f8f8` | 상/하단 바 |
| Header gradient top | `BG_HEADER_A` | `#fff6f3` | 헤더 그라데이션 시작 |
| Header gradient bottom | `BG_HEADER_B` | `#ffffff` | 헤더 그라데이션 끝 |
| Action bar | `BG_ACTION` | `#f7f4ef` | 하단 실행 영역 |
| Subtle panel | `BG_SUBTLE` | `#faf8f5` | 경량 영역 |
| Ink 900 | `INK_900` | `#1a1814` | 본문 강조 |
| Ink 700 | `INK_700` | `#3a342c` | 본문 |
| Ink 500 | `INK_500` | `#7a7367` | 보조 텍스트 |
| Ink 400 | `INK_400` | `#9b9388` | 캡션 |
| Ink 300 | `INK_300` | `#c7bfb2` | 비활성 |
| Ink 200 | `INK_200` | `#e5ded0` | 테두리 |
| Ink 100 | `INK_100` | `#eeeae2` | 얕은 테두리 |
| Ink 50 | `INK_50` | `#f6f3ed` | 극옅은 배경 |
| **Accent** | `ACCENT` | `#e05543` | 브랜드(테라코타) |
| Accent dark | `ACCENT_DK` | `#c73a28` | 버튼 pressed |
| Accent tint | `ACCENT_TINT` | `#fef4f1` | 드롭존 기본 |
| Accent soft | `ACCENT_SOFT` | `#fdece8` | 드롭존 hover |
| Accent hover | `ACCENT_HOVER` | `#ea5d4b` | 버튼 그라데 상단 |
| Success | `SUCCESS` | `#3f8f5e` | 완료 강조 |
| Success bg | `SUCCESS_BG` | `#f0faf3` | 완료 패널 배경 |
| Success dark | `SUCCESS_DK` | `#1f5237` | 완료 제목 |
| Success mid | `SUCCESS_MID` | `#3d6b51` | 완료 본문 |
| Success border | `SUCCESS_BRD` | `#d5ead9` | 완료 테두리 |

### 폰트

- Sans: `Pretendard, "Malgun Gothic", "맑은 고딕", Segoe UI`
- Mono (수치·경로·버전): `Consolas, "Courier New", monospace`

크기 규칙:
- 창 타이틀: 12px / 500
- 섹션 헤더: 11px / 700 / letter-spacing 1px (대문자 느낌)
- 본문 값: 12~13px / 600
- 캡션: 10~11px / 400
- 버튼: 12~13px / 600~700

### 반경 / 간격

- 큰 프레임: `8~10px` border-radius
- 카드/버튼: `6~8px`
- 배지 (pill): `999px`
- 모서리 kbd: `4px`
- 컨텐츠 패딩: 외곽 24px, 섹션 간 18~20px, 위젯 내부 10~14px

---

## 2. 창 레이아웃 골격

모든 화면은 아래 5층 구조:

```
┌─────────────────────────────────┐
│ titleBar      34px 고정          │  ← 드래그 이동, min/max/close 버튼
├─────────────────────────────────┤
│ appHeader     브랜드마크 + 타이틀 │  ← 그라데이션 배경
├─────────────────────────────────┤
│                                 │
│ main          drop zone +       │  ← 가변 stretch=1
│               파일 목록 +         │
│               품질 세그먼트       │
│                                 │
├─────────────────────────────────┤
│ bottomStack   action /          │  ← QStackedWidget으로 교체
│               progress /        │
│               success            │
├─────────────────────────────────┤
│ statusRail    28px 고정          │  ← "오프라인 모드" + 스택 정보
└─────────────────────────────────┘
```

- **프레임리스**: `FramelessWindowHint` — 타이틀바 직접 구현
- 반투명 X — 솔리드 배경 + 1px `INK_200` 테두리
- 기본 사이즈: 820×720 (앱 성격에 맞게 조정)

---

## 3. 커스텀 QPainter 위젯 카탈로그

모두 `main_window.py` 상단에 `QLabel/QWidget` 상속으로 구현됨. 그대로 복사 가능.

| 클래스 | 크기 | 용도 | 재사용성 |
|--------|-----|------|---------|
| `BrandMark` | 36×36 | 좌상단 앱 로고 (accent 사각형 + 파일 아이콘) | 아이콘 모양만 교체 |
| `PdfIcon` | 가변 | 파일 목록 행 앞 아이콘 | 파일 타입별 바꿔쓰기 |
| `PlusCircle` | 44×44 | 드롭존 중앙 "+ 원형" | 그대로 재사용 |
| `PulsingDot` | 8×8 | 진행 중 펄싱 점 (QTimer 애니메이션) | 그대로 재사용 |
| `CheckIcon` | 36×36 | 완료 체크 아이콘 (초록 원 + 흰 체크) | 그대로 재사용 |
| `RatioBar` | 가변 | 셀 안에 들어가는 감소율 프로그레스 바 | 그대로 재사용 |
| `FileNameCell` | 가변 | PdfIcon + 파일명 라벨 | 아이콘만 교체 |
| `DropZone` | 108px | 드래그·클릭 영역 + hover/active 상태 | 그대로 재사용 |
| `QualityCard` | 가변 | 품질 세그먼트의 3등분 카드 | 그대로 재사용 |

**핵심**: `PlusCircle`, `PulsingDot`, `CheckIcon`, `RatioBar`, `DropZone`, `QualityCard` 6개는 도메인 불문 재사용.

---

## 4. QSS 핵심 패턴

### 패턴 A — 동적 속성 기반 상태 스타일

QSS는 Qt의 dynamic property를 셀렉터로 씁니다. hover/active/working/pending 등 상태를 코드에서 `setProperty("state", "true")` + `unpolish/polish` 로 토글.

```css
#dropZone { background: #fef4f1; border: 2px dashed rgba(224,85,67,0.45); }
#dropZone[hover="true"] { background: #fdece7; border: 2px dashed #e05543; }
#dropZone[dragActive="true"] { background: #fde5df; border: 2px solid #e05543; }
```

```python
def enterEvent(self, _ev):
    self.setProperty("hover", "true")
    self.style().unpolish(self); self.style().polish(self)
```

### 패턴 B — 그라데이션 버튼

```css
QPushButton#btnCompress {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                                stop:0 #ea5d4b, stop:1 #e05543);
    border: 1px solid rgba(199,58,40,0.25);
    border-radius: 8px;
    padding: 10px 22px;
}
QPushButton#btnCompress:hover { ... stop:0 #ef6551 ... }
QPushButton#btnCompress:pressed { background: #c73a28; }
QPushButton#btnCompress:disabled { background: #e5ded0; color: #9b9388; }
```

### 패턴 C — kbd 키 스타일 pill (드롭존 안내용)

```html
<span style='background:white; border:1px solid #e5ded0;
             border-radius:4px; padding:1px 6px;
             font-family:Consolas, monospace; font-size:10px;'>클릭</span>
```

Qt `QLabel`에 `Qt.TextFormat.RichText` 로 주면 HTML이 그대로 렌더됨.

---

## 5. 상태 관리 패턴

### 5-1. 파일 리스트 박스 크기 고정 (`QStackedLayout`)

**문제**: 빈 상태 ↔ 테이블 전환 시 박스 크기가 들쭉날쭉.
**해결**: 같은 공간에 두 위젯을 겹쳐둠.

```python
list_wrap = QFrame()
list_wrap.setMinimumHeight(220)
list_stack = QStackedLayout(list_wrap)
list_stack.addWidget(empty_state)   # index 0
list_stack.addWidget(table)         # index 1

# 파일 추가/삭제 시:
list_stack.setCurrentIndex(0 if n == 0 else 1)
```

### 5-2. 하단 패널(`QStackedWidget`) 높이 자동 수축

**문제**: `QStackedWidget`은 가장 큰 자식 높이로 고정 → action 패널이 progress 패널 높이에 억지로 맞춰짐.
**해결**: **보이는 패널만 `Preferred`, 나머지 `Ignored`** + `currentChanged` 시점에 재적용.

```python
def _on_stack_changed(idx):
    for i in range(bottom_stack.count()):
        w = bottom_stack.widget(i)
        w.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred if i == idx else QSizePolicy.Policy.Ignored,
        )
        w.adjustSize()
    bottom_stack.adjustSize()

bottom_stack.currentChanged.connect(_on_stack_changed)
```

### 5-3. "새 작업" 리셋 버튼

완료 패널에 "＋ 새 압축" 버튼 → 테이블 비우고 `bottom_stack.setCurrentWidget(action_panel)`.

```python
def _start_new_run(self):
    self.table.setRowCount(0)
    self.files.clear()
    self._update_count()
    self.bottom_stack.setCurrentWidget(self.action_panel)
```

---

## 6. QThread 백그라운드 작업 패턴

UI freeze 방지 — 압축/리사이즈 등 무거운 작업은 반드시 `QThread` + `pyqtSignal`.

```python
class CompressionWorker(QThread):
    fileStarted  = pyqtSignal(int, str)            # idx, filename
    fileProgress = pyqtSignal(int, float)          # idx, overall_pct
    fileDone     = pyqtSignal(int, int, int, float) # idx, in_sz, out_sz, ratio
    fileError    = pyqtSignal(int, str)
    allDone      = pyqtSignal(int, int, int)

    def __init__(self, entries, mode, output_dir):
        super().__init__()
        self.entries = entries; self.mode = mode; self.output_dir = output_dir

    def run(self):
        for fi, (idx, path) in enumerate(self.entries):
            self.fileStarted.emit(idx, os.path.basename(path))
            def cb(cur, tot, fi=fi):
                self.fileProgress.emit(idx, (fi + cur/max(tot,1)) / total * 100)
            try:
                in_sz, out_sz = compress_one(path, out, self.mode, cb)
                self.fileDone.emit(idx, in_sz, out_sz, ratio)
            except Exception as e:
                self.fileError.emit(idx, str(e))
        self.allDone.emit(total, tot_orig, tot_comp)
```

메인 스레드에서 시그널에 핸들러 연결:

```python
self._worker = CompressionWorker(...)
self._worker.fileStarted.connect(self._on_file_started)
self._worker.fileProgress.connect(self._on_file_progress)
self._worker.fileDone.connect(self._on_file_done)
self._worker.allDone.connect(self._on_all_done)
self._worker.start()
```

---

## 7. 드래그 앤 드롭 패턴

```python
class DropZone(QFrame):
    filesDropped = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        paths = [url.toLocalFile() for url in ev.mimeData().urls()
                 if self._is_supported(url.toLocalFile())]
        if paths:
            self.filesDropped.emit(paths)

    def _is_supported(self, p):
        return os.path.isfile(p) and p.lower().endswith(
            (".jpg", ".jpeg", ".png", ".webp"))   # 사진 압축기용
```

---

## 8. 사진 압축기 적용 체크리스트

`ui/main_window.py` 복사 후 **딱 6군데만** 치환하면 됩니다.

| # | 위치 | PDF 압축기 | 사진 압축기로 변경 |
|---|------|-----------|-------------------|
| 1 | `self.setWindowTitle(...)` | `"PDF 압축기"` | `"사진 압축기"` |
| 2 | 앱 헤더 `brandTitle` | `"PDF 압축기"` | `"사진 압축기"` |
| 3 | `BrandMark` 내부 그리기 | `"PDF"` 텍스트 | 카메라 또는 `"IMG"` |
| 4 | 드롭존 확장자 필터 | `.pdf` | `.jpg .jpeg .png .webp` |
| 5 | `QualityCard.Spec` 3개 | `900px Q35 / 1600px Q65 / 2400px Q85` | 사진용 DPI/품질 (예: `1280px Q60 / 1920px Q80 / 2560px Q90`) |
| 6 | `core/compressor.py` | Ghostscript/PyMuPDF | **Pillow 기반 이미지 리사이즈 + JPEG/WebP 재인코딩** |

그 외(스타일·레이아웃·QThread·DropZone·QStackedLayout 등)는 **그대로**.

### 사진 압축기용 `core/compressor.py` 골격 (참고)

```python
from PIL import Image, ImageOps

PROFILES = {
    "extreme":     {"max_dim": 1280, "quality": 60},
    "recommended": {"max_dim": 1920, "quality": 80},
    "low":         {"max_dim": 2560, "quality": 90},
}

def compress_image(input_path, output_path, mode, progress_cb=None):
    in_sz = os.path.getsize(input_path)
    prof = PROFILES.get(mode, PROFILES["recommended"])

    img = Image.open(input_path)
    img = ImageOps.exif_transpose(img)   # EXIF 방향 보정
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    w, h = img.size
    m = prof["max_dim"]
    if w > m or h > m:
        scale = m / max(w, h)
        img = img.resize((int(w*scale), int(h*scale)), Image.LANCZOS)

    img.save(output_path, format="JPEG",
             quality=prof["quality"], optimize=True, progressive=True)

    if progress_cb:
        progress_cb(1, 1)
    return in_sz, os.path.getsize(output_path)
```

배치 처리 시 `CompressionWorker.run()` 루프 내부에서 `compress_image` 를 부르면 됩니다 (현재 PDF 버전과 완전히 동일한 워커 구조).

---

## 9. 빌드 / 배포

### `requirements.txt`
```
Pillow>=10.0.0
PyQt6>=6.6.0
```

### `build.bat` (PyInstaller)
```bat
pyinstaller --onefile --windowed ^
    --name "사진압축기" ^
    --icon "assets/icon.ico" ^
    --collect-all PyQt6 ^
    app.py
```

PDF 버전의 `--collect-all pymupdf`, `--collect-all pikepdf`, Ghostscript add-data는 전부 제거 가능 → **exe 크기가 218MB에서 30~40MB로 줄어듬**.

### GitHub 릴리즈 (PDF와 동일 흐름)
```bash
git tag v1.0.0
git push origin v1.0.0
gh release create v1.0.0 dist/사진압축기.exe --title "v1.0.0" --notes "..."
```

---

## 10. 재사용 가능한 파일 목록 (체크)

PDF 압축기 프로젝트에서 **그대로 복사해도 되는 파일**:

- [x] `ui/styles.py` — 토큰 + QSS (색만 바꾸고 싶으면 상단 토큰 15개만 수정)
- [x] `ui/main_window.py` 내부의 다음 클래스:
  - `BrandMark`, `PdfIcon` (이름/모양만 교체), `PlusCircle`, `PulsingDot`, `CheckIcon`
  - `RatioBar`, `FileNameCell`, `DropZone`, `QualityCard`
  - `CompressionWorker` (엔진 함수 호출만 교체)
  - `MainWindow` 의 `_build_titlebar`, `_build_app_header`, `_build_main` 골격,
    `_build_bottom_stack`, `_build_status_rail`, 모든 `_on_*` 슬롯
- [x] `app.py` — 엔트리 포인트 (앱 이름만 변경)
- [x] `.gitignore`, `run.bat` 골격

**새로 써야 하는 것**: `core/compressor.py` (§8 참고), 앱 아이콘.

---

## 11. 자주 밟는 지뢰 (미리 피하기)

1. **`QPushButton` + 자식 레이아웃 금지** — 버튼이 자기 텍스트를 자식 위에 덧그림. 커스텀 카드는 `QFrame` + `mousePressEvent`로.
2. **`WA_TranslucentBackground` 사용 금지** — 프레임리스에서 투명 배경을 켜면 윈도우가 스냅/사이즈 조절 시 깜빡임. 솔리드 배경 + 1px 테두리로 충분.
3. **QStackedWidget 안에 키 큰 위젯** — `Ignored` sizePolicy 트릭 없이 쓰면 작은 패널이 늘어남 (§5-2).
4. **kbd 스타일을 HBoxLayout 3개 라벨로 구성하면 정렬 깨짐** — 단일 QLabel + rich text가 안정적.
5. **드래그 중 이벤트 누락** — `dragEnterEvent`에서 반드시 `acceptProposedAction()` 호출 안 하면 `dropEvent`가 안 옴.

---

작성: 2026-04-24 · PDF 압축기 v1.7.0 기준
