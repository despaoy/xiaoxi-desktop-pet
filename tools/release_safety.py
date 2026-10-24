"""Fail-closed, read-only guard for a distributable desktop build.

Run before PyInstaller (which replaces its output) and after it. Never clean a
user's data automatically. This guard covers known local-data paths and SQLite
artifacts; it is not a general scanner for arbitrary private content.
"""
from pathlib import Path
import argparse
import os
import stat

DATA_NAMES = {'data', 'data-tests', 'data-smoke', 'render-cache'}
DB_SUFFIXES = ('.sqlite', '.sqlite3', '.db', '.sqlite-wal', '.sqlite-shm',
               '.sqlite3-wal', '.sqlite3-shm', '.db-wal', '.db-shm',
               '.sqlite-journal', '.sqlite3-journal', '.db-journal')


def is_link(path):
    metadata = path.lstat()  # Propagate permission/I/O errors, never treat as clean.
    return (stat.S_ISLNK(metadata.st_mode) or
            bool(getattr(metadata, 'st_file_attributes', 0) &
                 getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)))


def audit_distribution(directory):
    root = Path(directory)
    try:
        root_metadata = root.lstat()
    except FileNotFoundError:
        return []  # A first build has no output yet.
    if is_link(root):
        raise ValueError('Distribution directory must not be a link or reparse point')
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise ValueError('Distribution path is not a directory')
    findings = []
    pending = [root]
    while pending:
        # pathlib glob suppresses some scandir errors. Explicit traversal makes
        # an unreadable subtree fail the entire audit instead of looking clean.
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                path = Path(entry.path)
                name = entry.name.lower()
                linked = is_link(path)
                if (linked or name in DATA_NAMES or
                        name.endswith(DB_SUFFIXES) or name == 'app.log'):
                    findings.append(path.relative_to(root).as_posix())
                if not linked and entry.is_dir(follow_symlinks=False):
                    pending.append(path)
    return sorted(findings)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--require-output', action='store_true')
    args = parser.parse_args(argv)
    if args.require_output and not args.directory.is_dir():
        parser.exit(1, 'Release audit failed: build output is missing.\n')
    try:
        findings = audit_distribution(args.directory)
    except (OSError, ValueError) as error:
        parser.exit(1, f'Release audit failed: {error}\n')
    if findings:
        parser.exit(1, 'Release audit blocked: local data or links found. '
                    'Back up this output and choose a clean build directory; '
                    'nothing was deleted.\n' + '\n'.join(findings) + '\n')
    print('Release audit passed: no known local data paths or SQLite artifacts.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
