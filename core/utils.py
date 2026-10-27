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


def unique_output_paths(input_paths: list[str], output_dir: str) -> list[str]:
    """Output path per input, de-duplicated within the batch.

    다른 폴더의 같은 이름 파일이 한 저장 폴더에서 서로 덮어쓰지 않도록 (2), (3)… 을 붙인다.
    """
    taken: set[str] = set()
    result = []
    for path in input_paths:
        candidate = get_output_path(path, output_dir)
        stem, ext = os.path.splitext(candidate)
        n = 2
        while os.path.normcase(candidate) in taken:
            candidate = f"{stem} ({n}){ext}"
            n += 1
        taken.add(os.path.normcase(candidate))
        result.append(candidate)
    return result


def collect_files(paths: list[str], extensions: tuple[str, ...]) -> list[str]:
    """Expand dropped/selected paths: folders are searched recursively."""
    result = []
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, names in os.walk(p):
                for name in sorted(names):
                    if name.lower().endswith(extensions):
                        result.append(os.path.normpath(os.path.join(root, name)))
        elif os.path.isfile(p) and p.lower().endswith(extensions):
            result.append(os.path.normpath(p))
    return result


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)
