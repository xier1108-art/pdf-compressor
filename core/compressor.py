"""
PDF compression engine.
Stage 1 – PyMuPDF: re-encode embedded images at lower quality / smaller dimensions.
Stage 2 – PyMuPDF save flags: deflate all streams, garbage-collect duplicates.
Stage 3 – pikepdf: structural cleanup (metadata, thumbnails, object streams).
"""

import io
import os

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


# Compression profiles: max image dimension (px), JPEG quality, min image bytes to process
PROFILES = {
    "extreme":     {"max_dim": 900,  "quality": 35, "min_bytes": 2_048},
    "recommended": {"max_dim": 1600, "quality": 65, "min_bytes": 4_096},
    "low":         {"max_dim": 2400, "quality": 85, "min_bytes": 8_192},
}


def compress_pdf(input_path: str, output_path: str,
                 mode: str = "recommended",
                 progress_callback=None) -> tuple[int, int]:
    """
    Compress a PDF file and save to output_path.

    Args:
        input_path:        source PDF path
        output_path:       destination PDF path
        mode:              'extreme' | 'recommended' | 'low'
        progress_callback: callable(current_page, total_pages) or None

    Returns:
        (input_size_bytes, output_size_bytes)

    Raises:
        RuntimeError if PyMuPDF is not installed.
    """
    if not HAS_PYMUPDF:
        raise RuntimeError(
            "PyMuPDF가 설치되지 않았습니다. 'pip install pymupdf' 를 실행하세요."
        )

    profile = PROFILES.get(mode, PROFILES["recommended"])
    input_size = os.path.getsize(input_path)

    doc = fitz.open(input_path)
    total_pages = len(doc)

    if HAS_PIL:
        _recompress_images(doc, profile, progress_callback, total_pages)
    elif progress_callback:
        # Still report progress even without image recompression
        for i in range(total_pages):
            progress_callback(i + 1, total_pages)

    doc.save(
        output_path,
        garbage=4,           # remove unused + deduplicate objects
        deflate=True,        # compress all streams
        deflate_images=True,
        deflate_fonts=True,
        clean=True,          # sanitize content streams
    )
    doc.close()

    if HAS_PIKEPDF:
        _pikepdf_cleanup(output_path, mode)

    output_size = os.path.getsize(output_path)
    return input_size, output_size


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _recompress_images(doc, profile, progress_callback, total_pages):
    """Iterate every page, re-encode large images as JPEG at reduced quality."""
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
                pass  # never break the PDF; just leave this image as-is

        if progress_callback:
            progress_callback(page_num + 1, total_pages)


def _recompress_one(doc, xref, profile):
    """Re-encode a single image xref as JPEG if it saves space."""
    base = doc.extract_image(xref)
    if not base:
        return

    img_data = base.get("image", b"")
    if len(img_data) < profile["min_bytes"]:
        return

    # Open with Pillow
    pil_img = Image.open(io.BytesIO(img_data))

    # Convert to RGB (JPEG cannot store alpha or CMYK directly)
    if pil_img.mode == "RGBA":
        bg = Image.new("RGB", pil_img.size, (255, 255, 255))
        bg.paste(pil_img, mask=pil_img.split()[3])
        pil_img = bg
    elif pil_img.mode in ("LA", "PA"):
        pil_img = pil_img.convert("RGBA")
        bg = Image.new("RGB", pil_img.size, (255, 255, 255))
        bg.paste(pil_img, mask=pil_img.split()[3])
        pil_img = bg
    elif pil_img.mode in ("P", "L", "CMYK"):
        pil_img = pil_img.convert("RGB")
    elif pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")

    # Scale down if any dimension exceeds the profile maximum
    w, h = pil_img.size
    max_dim = profile["max_dim"]
    if w > max_dim or h > max_dim:
        scale = max_dim / max(w, h)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
    else:
        new_w, new_h = w, h

    # Encode as JPEG
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=profile["quality"],
                 optimize=True, progressive=True)
    jpeg_bytes = buf.getvalue()

    # Only replace if it actually saves space
    if len(jpeg_bytes) >= len(img_data):
        return

    # Update the raw stream and fix the image dictionary
    doc.update_stream(xref, jpeg_bytes, raw=True)
    doc.xref_set_key(xref, "Filter", "/DCTDecode")
    doc.xref_set_key(xref, "ColorSpace", "/DeviceRGB")
    doc.xref_set_key(xref, "Width", str(new_w))
    doc.xref_set_key(xref, "Height", str(new_h))
    doc.xref_set_key(xref, "BitsPerComponent", "8")
    # JPEG doesn't use DecodeParms – set to null to remove it
    try:
        doc.xref_set_key(xref, "DecodeParms", "null")
    except Exception:
        pass


def _pikepdf_cleanup(path: str, mode: str):
    """Post-process with pikepdf: strip metadata, thumbnails, compress streams."""
    try:
        with pikepdf.open(path, allow_overwriting_input=True) as pdf:
            # Clear document info dictionary
            try:
                del pdf.docinfo
            except Exception:
                try:
                    pdf.docinfo.clear()
                except Exception:
                    pass

            # Remove embedded page thumbnails
            for page in pdf.pages:
                for key in ("/Thumb", "/PieceInfo"):
                    if key in page:
                        try:
                            del page[key]
                        except Exception:
                            pass

            pdf.save(
                path,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
                recompress_flate=True,
            )
    except Exception:
        pass  # PyMuPDF output is still valid even if pikepdf fails
