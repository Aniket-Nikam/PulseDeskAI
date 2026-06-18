import io
import logging
from typing import Optional, Tuple
from PIL import Image

log = logging.getLogger("screen_capture")

def capture_primary_screen(
    max_width: Optional[int] = None, 
    quality: int = 60, 
    format_type: str = "JPEG"
) -> Tuple[Optional[bytes], str]:
    """
    Captures the primary monitor screen.
    Returns:
        (image_bytes, mime_type) or (None, "") if capture fails.
    """
    # 1. Try capturing with mss (high performance)
    try:
        import mss
        import mss.tools
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            img = sct.grab(monitor)
            
            # If no resizing needed and we want PNG, mss.tools is fastest
            if max_width is None and format_type.upper() == "PNG":
                buf = io.BytesIO()
                buf.write(mss.tools.to_png(img.rgb, img.size))
                return buf.getvalue(), "image/png"
            
            # Convert BGRA to RGB via PIL for resizing or compression
            pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
    except Exception as e:
        log.debug(f"mss capture failed, falling back to PIL: {e}")
        # 2. Fallback to PIL ImageGrab (standard library / Pillow fallback)
        try:
            from PIL import ImageGrab
            pil_img = ImageGrab.grab()
        except Exception as ex:
            log.warning(f"Screen capture failed completely: {ex}")
            return None, ""

    # Downscale if max_width is specified
    if max_width and pil_img.width > max_width:
        ratio = float(max_width) / pil_img.width
        new_height = int(pil_img.height * ratio)
        pil_img = pil_img.resize((max_width, new_height), Image.Resampling.BILINEAR)

    # Save to buffer
    buf = io.BytesIO()
    fmt = format_type.upper()
    mime = "image/png" if fmt == "PNG" else "image/jpeg"
    
    pil_img.save(buf, format=fmt, quality=quality)
    return buf.getvalue(), mime
