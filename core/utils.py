import os


def format_size(bytes_val: int) -> str:
    """Format byte count as human-readable string."""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    else:
        return f"{bytes_val / (1024 * 1024):.1f} MB"


def get_file_size(path: str) -> int:
    return os.path.getsize(path)


def get_output_path(input_path: str, output_dir: str) -> str:
    """Return output file path: <output_dir>/<name>_compressed.pdf"""
    basename = os.path.basename(input_path)
    name, ext = os.path.splitext(basename)
    return os.path.join(output_dir, f"{name}_compressed{ext}")


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)
