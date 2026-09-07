"""Verify a restored evidence directory against JSON attachment metadata on stdin."""
import json
from pathlib import Path
import sys


def verify(directory, rows):
    root = Path(directory).resolve()
    errors = []
    for row in rows:
        name = row.get('stored_name') or Path(row.get('file_path') or '').name
        if not name or Path(name).name != name:
            errors.append(f"Attachment {row['id']} has an unsafe filename")
            continue
        path = root / name
        if not path.is_file() or path.is_symlink():
            errors.append(f"Attachment {row['id']} is missing from the archive")
        elif path.stat().st_size != int(row.get('size_bytes') or 0):
            errors.append(f"Attachment {row['id']} has a size mismatch")
    if errors:
        raise ValueError('\n'.join(errors))
    return len(rows)


if __name__ == '__main__':
    try:
        count = verify(sys.argv[1], json.load(sys.stdin))
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc))
    print(f'Attachment references verified: {count}')
