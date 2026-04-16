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
# 핵심 전략: /screen 프리셋(공격적 JPEG 품질)을 기본으로 쓰고,
# DPI만 모드별로 명시적으로 덮어씀.
# /ebook 프리셋은 150 DPI지만 JPEG 품질이 보수적이라 압축률이 낮음.
# /screen 기반에서 DPI를 높이면 화질은 유지하면서 압축률도 확보됨.
#
# 실측 (3520×2464 스캔 PDF 11MB 기준):
#   extreme  (72 DPI)  → ~1.2 MB  (89%)
#   recommended (150 DPI) → ~3.9 MB (64%)  ← ilovepdf 수준
#   low      (200 DPI) → ~6.0 MB  (45%)
_GS_DPI = {
    "extreme":     72,
    "recommended": 150,
    "low":         200,
}


def _gs_mode_args(mode: str) -> list[str]:
    """Return explicit Ghostscript parameters for the given compression mode."""
    dpi = _GS_DPI.get(mode, 150)
    return [
        "-dPDFSETTINGS=/screen",           # 공격적 JPEG 품질 베이스
        # 이미지 다운샘플 강제 적용
        "-dDownsampleColorImages=true",
        "-dDownsampleGrayImages=true",
        "-dDownsampleMonoImages=true",
        f"-dColorImageResolution={dpi}",   # /screen 기본 72 DPI 덮어쓰기
        f"-dGrayImageResolution={dpi}",
        f"-dMonoImageResolution={dpi}",
        "-dColorImageDownsampleType=/Bicubic",
        "-dGrayImageDownsampleType=/Bicubic",
        # AutoFilter 끄고 JPEG 인코딩 강제 — 이게 없으면 Flate(무손실)로 남아 압축 미적용
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
    Build environment for GS subprocess.
    When running from a PyInstaller bundle, GS_LIB must point to the
    bundled lib/ directory so Ghostscript can find its PS library files.
    """
    env = os.environ.copy()
    if hasattr(sys, "_MEIPASS"):
        gs_base = os.path.join(sys._MEIPASS, "gs")
        env["GS_LIB"] = os.path.join(gs_base, "lib")
        env["GS_FONTPATH"] = os.path.join(gs_base, "Resource", "Font")
    return env


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

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_gs_env(gs_path),
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
