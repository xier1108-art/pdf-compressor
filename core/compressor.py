"""
PDF compression engine.

Primary engine  – Ghostscript (when installed):
    Full PDF re-rendering pipeline; re-encodes ALL images, subsets fonts,
    strips ICC profiles, removes unused objects.  Achieves 50-90% reduction.

Fallback engine – PyMuPDF + pikepdf:
    Image-level recompression only.  Achieves 10-40% on image-heavy PDFs.
"""

import glob
import io
import os
import re
import shutil
import subprocess
import sys

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    import pikepdf
    HAS_PIKEPDF = True
except ImportError:
    HAS_PIKEPDF = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# ---------------------------------------------------------------------------
# Ghostscript mode arguments
# ---------------------------------------------------------------------------
# extreme / recommended:
#   /screen 베이스(공격적 JPEG 품질) + JPEG 강제 인코딩 + DPI 명시 오버라이드
#   → 이미 JPEG로 저장된 이미지도 재압축, 큰 압축률 확보
#
# low:
#   /printer 베이스(고품질, 300 DPI) + AutoFilter ON(GS가 인코딩 방식 자동 선택)
#   + DPI만 200으로 명시 오버라이드
#   → 이미 잘 압축된 이미지는 건드리지 않고, 해상도만 낮춰 구조 정리 중심 압축
#   → JPEG 강제 인코딩 없으므로 어떤 파일이든 오히려 커지지 않음


def _gs_mode_args(mode: str) -> list[str]:
    """Return explicit Ghostscript parameters for the given compression mode.

    세 모드 모두 /screen 베이스 + JPEG 강제 인코딩을 사용하고 DPI만 다르게 설정.
    - /printer·/ebook 베이스는 AutoFilter가 켜져 있어 이미 압축된 이미지를
      무손실(Flate)로 남겨두므로, Flate+JPEG 이중 인코딩 구조의 PDF에서
      오히려 파일이 커지는 문제가 있음.
    - /screen + AutoFilter OFF + JPEG 강제 인코딩이 유일하게 안정적으로 압축됨.
    - DPI로 화질/크기 균형을 조절:
        extreme  72 DPI  → 최대 압축 (~89%)
        recommended 150 DPI → 균형 (~64%)
        low      200 DPI → 화질 우선 (~44%)
    """
    dpi = {"extreme": 72, "recommended": 150, "low": 200}.get(mode, 150)
    return [
        "-dPDFSETTINGS=/screen",
        "-dDownsampleColorImages=true",
        "-dDownsampleGrayImages=true",
        "-dDownsampleMonoImages=true",
        f"-dColorImageResolution={dpi}",
        f"-dGrayImageResolution={dpi}",
        f"-dMonoImageResolution={dpi}",
        "-dColorImageDownsampleType=/Bicubic",
        "-dGrayImageDownsampleType=/Bicubic",
        # JPEG 강제 인코딩 — Flate로 남는 이미지를 확실히 재압축
        "-dAutoFilterColorImages=false",
        "-dColorImageFilter=/DCTEncode",
        "-dAutoFilterGrayImages=false",
        "-dGrayImageFilter=/DCTEncode",
    ]

# PyMuPDF fallback profiles
PYMUPDF_PROFILES = {
    "extreme":     {"max_dim": 900,  "quality": 35, "min_bytes": 0},
    "recommended": {"max_dim": 1600, "quality": 65, "min_bytes": 0},
    "low":         {"max_dim": 2400, "quality": 85, "min_bytes": 0},
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_ghostscript() -> str | None:
    """Return path to the Ghostscript executable, or None if not found."""
    # 0) PyInstaller bundle: GS shipped inside the .exe
    if hasattr(sys, "_MEIPASS"):
        bundled = os.path.join(sys._MEIPASS, "gs", "bin", "gswin64c.exe")
        if os.path.isfile(bundled):
            return bundled

    # 1) Common Windows install paths (newest version wins)
    patterns = [
        r"C:/Program Files/gs/gs*/bin/gswin64c.exe",
        r"C:/Program Files (x86)/gs/gs*/bin/gswin32c.exe",
        r"C:/Program Files/gs/gs*/bin/gswin32c.exe",
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            return sorted(matches)[-1]

    # 2) Windows registry
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\GPL Ghostscript") as key:
            version = winreg.EnumKey(key, 0)
            dll_path, _ = winreg.QueryValueEx(
                winreg.OpenKey(key, version), "GS_DLL")
            bin_dir = os.path.dirname(dll_path)
            for name in ("gswin64c.exe", "gswin32c.exe"):
                exe = os.path.join(bin_dir, name)
                if os.path.isfile(exe):
                    return exe
    except Exception:
        pass

    # 3) PATH
    for cmd in ("gswin64c", "gswin32c", "gs"):
        path = shutil.which(cmd)
        if path:
            return path

    return None


def _gs_env(gs_path: str) -> dict:
    """
    Build a minimal, clean environment for the GS subprocess.

    문제: PyInstaller .exe 실행 시 _MEIPASS 폴더(pymupdf·numpy·PIL DLL 수십 개)가
    PATH에 포함된 채로 gswin64c.exe 서브프로세스가 뜨면, Windows DLL 로더가
    그 DLL들까지 추가 로드하여 TLS(Thread Local Storage) 슬롯이 고갈됨.
    → R6016 "not enough space for thread data" 런타임 오류 발생.

    해결: GS 전용 최소 PATH만 사용하고 _MEIPASS 경로를 완전히 차단.
    """
    gs_bin = os.path.dirname(os.path.abspath(gs_path))

    if hasattr(sys, "_MEIPASS"):
        gs_base = os.path.join(sys._MEIPASS, "gs")
    else:
        gs_base = os.path.dirname(gs_bin)  # gs10.x.x/ 루트

    sys_root = os.environ.get("SystemRoot", r"C:\Windows")
    minimal_path = ";".join([
        gs_bin,
        os.path.join(sys_root, "System32"),
        os.path.join(sys_root, "SysWOW64"),
        sys_root,
    ])

    return {
        "PATH":        minimal_path,
        "GS_LIB":      os.path.join(gs_base, "lib"),
        "GS_FONTPATH": os.path.join(gs_base, "Resource", "Font"),
        "SystemRoot":  sys_root,
        "SystemDrive": os.environ.get("SystemDrive", "C:"),
        "TEMP":        os.environ.get("TEMP", ""),
        "TMP":         os.environ.get("TMP", ""),
        "USERPROFILE": os.environ.get("USERPROFILE", ""),
        "APPDATA":     os.environ.get("APPDATA", ""),
        "USERNAME":    os.environ.get("USERNAME", ""),
    }


def get_engine() -> str:
    """Return 'ghostscript' or 'pymupdf' depending on what's available."""
    return "ghostscript" if find_ghostscript() else "pymupdf"


def compress_pdf(input_path: str, output_path: str,
                 mode: str = "recommended",
                 progress_callback=None) -> tuple[int, int]:
    """
    Compress a PDF file and save to output_path.

    Returns (input_size_bytes, output_size_bytes).
    Uses Ghostscript when available, falls back to PyMuPDF.
    """
    input_size = os.path.getsize(input_path)

    gs_path = find_ghostscript()
    if gs_path:
        _compress_ghostscript(gs_path, input_path, output_path,
                               mode, progress_callback)
    else:
        if not HAS_PYMUPDF:
            raise RuntimeError(
                "Ghostscript도 PyMuPDF도 없습니다.\n"
                "'pip install pymupdf' 를 실행하거나 Ghostscript를 설치하세요."
            )
        _compress_pymupdf(input_path, output_path, mode, progress_callback)

    output_size = os.path.getsize(output_path)

    # 압축 결과가 원본보다 크면 원본을 그대로 복사
    if output_size > input_size:
        shutil.copy2(input_path, output_path)
        output_size = input_size

    return input_size, output_size


# ---------------------------------------------------------------------------
# Ghostscript engine
# ---------------------------------------------------------------------------

def _compress_ghostscript(gs_path: str, input_path: str, output_path: str,
                           mode: str, progress_callback):
    """Run Ghostscript and parse 'Page N' lines for progress reporting."""
    total_pages = _get_page_count(input_path)

    cmd = [
        gs_path,
        "-dBATCH",
        "-dNOPAUSE",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.5",
        *_gs_mode_args(mode),
        # CJK/한글 폰트 유지
        "-dEmbedAllFonts=true",
        "-dSubsetFonts=true",
        f"-sOutputFile={output_path}",
        input_path,
    ]

    # Windows: hide console window that would flash when GS launches
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_gs_env(gs_path),
        cwd=os.path.dirname(os.path.abspath(gs_path)),  # gsdll64.dll 탐색 안정화
        creationflags=creationflags,
    )

    current_page = 0
    for line in proc.stdout:
        m = re.match(r"Page\s+(\d+)", line.strip())
        if m:
            current_page = int(m.group(1))
            if progress_callback and total_pages > 0:
                progress_callback(current_page, total_pages)

    proc.wait()

    if proc.returncode != 0:
        raise RuntimeError(f"Ghostscript 오류 (exit {proc.returncode})")

    # Final progress tick if GS didn't print page lines
    if progress_callback and current_page == 0 and total_pages > 0:
        progress_callback(total_pages, total_pages)


# ---------------------------------------------------------------------------
# PyMuPDF fallback engine
# ---------------------------------------------------------------------------

def _compress_pymupdf(input_path: str, output_path: str,
                      mode: str, progress_callback):
    """Image recompression + structural cleanup via PyMuPDF + pikepdf."""
    profile = PYMUPDF_PROFILES.get(mode, PYMUPDF_PROFILES["recommended"])

    doc = fitz.open(input_path)
    total_pages = len(doc)

    if HAS_PIL:
        _recompress_images(doc, profile, progress_callback, total_pages)
    elif progress_callback:
        for i in range(total_pages):
            progress_callback(i + 1, total_pages)

    doc.save(
        output_path,
        garbage=4,
        deflate=True,
        deflate_images=True,
        deflate_fonts=True,
        clean=True,
    )
    doc.close()

    if HAS_PIKEPDF:
        _pikepdf_cleanup(output_path)


def _recompress_images(doc, profile, progress_callback, total_pages):
    processed = set()
    for page_num in range(total_pages):
        page = doc[page_num]
        try:
            image_list = page.get_images(full=True)
        except Exception:
            image_list = []

        for img_info in image_list:
            xref = img_info[0]
            if xref in processed:
                continue
            processed.add(xref)
            try:
                _recompress_one(doc, xref, profile)
            except Exception:
                pass

        if progress_callback:
            progress_callback(page_num + 1, total_pages)


def _recompress_one(doc, xref, profile):
    base = doc.extract_image(xref)
    if not base:
        return

    img_data = base.get("image", b"")
    if len(img_data) < profile["min_bytes"]:
        return

    pil_img = Image.open(io.BytesIO(img_data))

    if pil_img.mode == "RGBA":
        bg = Image.new("RGB", pil_img.size, (255, 255, 255))
        bg.paste(pil_img, mask=pil_img.split()[3])
        pil_img = bg
    elif pil_img.mode in ("LA", "PA"):
        pil_img = pil_img.convert("RGBA")
        bg = Image.new("RGB", pil_img.size, (255, 255, 255))
        bg.paste(pil_img, mask=pil_img.convert("RGBA").split()[3])
        pil_img = bg
    elif pil_img.mode not in ("RGB",):
        pil_img = pil_img.convert("RGB")

    w, h = pil_img.size
    max_dim = profile["max_dim"]
    if w > max_dim or h > max_dim:
        scale = max_dim / max(w, h)
        pil_img = pil_img.resize(
            (max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    new_w, new_h = pil_img.size

    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=profile["quality"],
                 optimize=True, progressive=True)
    jpeg_bytes = buf.getvalue()

    if len(jpeg_bytes) >= len(img_data):
        return

    doc.update_stream(xref, jpeg_bytes, raw=True)
    doc.xref_set_key(xref, "Filter", "/DCTDecode")
    doc.xref_set_key(xref, "ColorSpace", "/DeviceRGB")
    doc.xref_set_key(xref, "Width", str(new_w))
    doc.xref_set_key(xref, "Height", str(new_h))
    doc.xref_set_key(xref, "BitsPerComponent", "8")
    try:
        doc.xref_set_key(xref, "DecodeParms", "null")
    except Exception:
        pass


def _pikepdf_cleanup(path: str):
    try:
        with pikepdf.open(path, allow_overwriting_input=True) as pdf:
            try:
                del pdf.docinfo
            except Exception:
                pass
            for page in pdf.pages:
                for key in ("/Thumb", "/PieceInfo"):
                    if key in page:
                        try:
                            del page[key]
                        except Exception:
                            pass
            pdf.save(path,
                     compress_streams=True,
                     object_stream_mode=pikepdf.ObjectStreamMode.generate,
                     recompress_flate=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _get_page_count(path: str) -> int:
    """Get PDF page count via PyMuPDF, or 0 if unavailable."""
    if not HAS_PYMUPDF:
        return 0
    try:
        doc = fitz.open(path)
        n = len(doc)
        doc.close()
        return n
    except Exception:
        return 0
