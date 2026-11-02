"""Tests for the single-purpose snapshot helper in tools/moneywiz-snapshot.

Each test compiles the helper with paths inside tmp_path and runs it against
synthetic SQLite databases; no real MoneyWiz data is involved.
"""

from collections.abc import Callable, Iterator
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import sys

import pytest

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(
        sys.platform != "darwin" or shutil.which("clang") is None,
        reason="snapshot helper is macOS-only and needs clang",
    ),
]

SOURCE_FILE = Path(__file__).resolve().parents[2] / (
    "tools/moneywiz-snapshot/moneywiz_snapshot.c"
)
SNAPSHOT_NAME = "snapshot.sqlite"


def _c_string(value: Path) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


@pytest.fixture
def build_helper(tmp_path) -> Callable[[Path, Path], Path]:
    def _build(source: Path, dest_dir: Path) -> Path:
        binary = tmp_path / "bin" / "moneywiz-snapshot"
        binary.parent.mkdir(exist_ok=True)
        subprocess.run(
            [
                "clang",
                "-std=c11",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                f"-DSNAPSHOT_SOURCE={_c_string(source)}",
                f"-DSNAPSHOT_DEST_DIR={_c_string(dest_dir)}",
                str(SOURCE_FILE),
                "-lsqlite3",
                "-o",
                str(binary),
            ],
            check=True,
            capture_output=True,
        )
        return binary

    return _build


@pytest.fixture
def wal_source(tmp_path) -> Iterator[tuple[Path, sqlite3.Connection]]:
    """A WAL-mode database whose latest rows exist only in the -wal file."""
    source = tmp_path / "Containers" / "ipadMoneyWiz.sqlite"
    source.parent.mkdir()
    conn = sqlite3.connect(source)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute("CREATE TABLE ZSYNCOBJECT (Z_PK INTEGER PRIMARY KEY, ZNAME TEXT)")
    conn.executemany(
        "INSERT INTO ZSYNCOBJECT (ZNAME) VALUES (?)", [(f"row{i}",) for i in range(50)]
    )
    conn.commit()
    # Keep the connection open so the WAL is not checkpointed into the main file
    yield source, conn
    conn.close()


def _run(binary: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(binary), *args], capture_output=True, text=True, check=False
    )


def _rows(path: Path) -> int:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        count: int = conn.execute("SELECT COUNT(*) FROM ZSYNCOBJECT").fetchone()[0]
        return count
    finally:
        conn.close()


def _leftover_temp_files(dest_dir: Path) -> list[Path]:
    return [p for p in dest_dir.iterdir() if p.name != SNAPSHOT_NAME]


class TestSnapshotHelper:
    def test_copies_committed_rows_still_in_wal(
        self, tmp_path, build_helper, wal_source
    ):
        source, _ = wal_source
        assert Path(f"{source}-wal").stat().st_size > 0
        dest_dir = tmp_path / "Application Support" / "moneywiz-mcp"
        dest_dir.parent.mkdir()
        binary = build_helper(source, dest_dir)

        result = _run(binary)

        assert result.returncode == 0, result.stderr
        assert _rows(dest_dir / SNAPSHOT_NAME) == 50

    def test_snapshot_is_single_private_file(self, tmp_path, build_helper, wal_source):
        source, _ = wal_source
        dest_dir = tmp_path / "out"
        binary = build_helper(source, dest_dir)

        assert _run(binary).returncode == 0

        snapshot = dest_dir / SNAPSHOT_NAME
        conn = sqlite3.connect(snapshot)
        try:
            assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        finally:
            conn.close()
        assert stat.S_IMODE(snapshot.stat().st_mode) == 0o600
        assert stat.S_IMODE(dest_dir.stat().st_mode) == 0o700
        assert _leftover_temp_files(dest_dir) == []

    def test_rerun_replaces_snapshot_with_new_data(
        self, tmp_path, build_helper, wal_source
    ):
        source, conn = wal_source
        dest_dir = tmp_path / "out"
        binary = build_helper(source, dest_dir)
        assert _run(binary).returncode == 0

        conn.execute("INSERT INTO ZSYNCOBJECT (ZNAME) VALUES ('new')")
        conn.commit()
        assert _run(binary).returncode == 0

        assert _rows(dest_dir / SNAPSHOT_NAME) == 51
        assert _leftover_temp_files(dest_dir) == []

    def test_tightens_existing_group_readable_directory(
        self, tmp_path, build_helper, wal_source
    ):
        source, _ = wal_source
        dest_dir = tmp_path / "out"
        dest_dir.mkdir(mode=0o755)
        dest_dir.chmod(0o755)
        binary = build_helper(source, dest_dir)

        assert _run(binary).returncode == 0
        assert stat.S_IMODE(dest_dir.stat().st_mode) == 0o700

    def test_rejects_arguments(self, tmp_path, build_helper, wal_source):
        source, _ = wal_source
        dest_dir = tmp_path / "out"
        binary = build_helper(source, dest_dir)

        result = _run(binary, "/etc/passwd")

        assert result.returncode == 2
        assert not dest_dir.exists()

    def test_refuses_symlinked_source(self, tmp_path, build_helper, wal_source):
        # A link planted in place of the database must not redirect the copy
        other, _ = wal_source
        source = tmp_path / "planted.sqlite"
        source.symlink_to(other)
        dest_dir = tmp_path / "out"
        binary = build_helper(source, dest_dir)

        result = _run(binary)

        assert result.returncode == 1
        assert not (dest_dir / SNAPSHOT_NAME).exists()
        assert _leftover_temp_files(dest_dir) == []

    def test_refuses_symlinked_destination_directory(
        self, tmp_path, build_helper, wal_source
    ):
        source, _ = wal_source
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        elsewhere.chmod(0o755)
        dest_dir = tmp_path / "out"
        dest_dir.symlink_to(elsewhere, target_is_directory=True)
        binary = build_helper(source, dest_dir)

        result = _run(binary)

        assert result.returncode == 1
        assert "symlinks are refused" in result.stderr
        # Nothing written to, or changed on, the link's target
        assert list(elsewhere.iterdir()) == []
        assert stat.S_IMODE(elsewhere.stat().st_mode) == 0o755

    def test_copies_closed_wal_database_without_side_files(
        self, tmp_path, build_helper
    ):
        # MoneyWiz closed: WAL header, but no -wal/-shm on disk
        source = tmp_path / "Mo ney%#?dir" / "ipadMoneyWiz.sqlite"
        source.parent.mkdir()
        conn = sqlite3.connect(source)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE ZSYNCOBJECT (Z_PK INTEGER PRIMARY KEY, ZNAME TEXT)")
        conn.executemany(
            "INSERT INTO ZSYNCOBJECT (ZNAME) VALUES (?)", [("a",), ("b",), ("c",)]
        )
        conn.commit()
        conn.close()
        assert not Path(f"{source}-wal").exists()
        assert not Path(f"{source}-shm").exists()
        dest_dir = tmp_path / "out"
        binary = build_helper(source, dest_dir)

        result = _run(binary)

        assert result.returncode == 0, result.stderr
        assert _rows(dest_dir / SNAPSHOT_NAME) == 3
        # The source directory was only read, never written to
        assert sorted(p.name for p in source.parent.iterdir()) == [source.name]

    def test_copies_rollback_journal_database(self, tmp_path, build_helper):
        source = tmp_path / "rollback.sqlite"
        conn = sqlite3.connect(source)
        conn.execute("CREATE TABLE ZSYNCOBJECT (Z_PK INTEGER PRIMARY KEY, ZNAME TEXT)")
        conn.execute("INSERT INTO ZSYNCOBJECT (ZNAME) VALUES ('x')")
        conn.commit()
        conn.close()
        dest_dir = tmp_path / "out"
        binary = build_helper(source, dest_dir)

        result = _run(binary)

        assert result.returncode == 0, result.stderr
        assert _rows(dest_dir / SNAPSHOT_NAME) == 1

    def test_refuses_unrecovered_wal_without_shared_memory(
        self, tmp_path, build_helper, wal_source
    ):
        # A crash can leave committed rows in -wal with no -shm. Copying the
        # main file alone would silently drop them, so the helper must refuse.
        live, _ = wal_source
        source = tmp_path / "crashed.sqlite"
        shutil.copyfile(live, source)
        shutil.copyfile(f"{live}-wal", f"{source}-wal")
        dest_dir = tmp_path / "out"
        binary = build_helper(source, dest_dir)

        result = _run(binary)

        assert result.returncode == 1
        assert "open MoneyWiz once" in result.stderr
        assert not (dest_dir / SNAPSHOT_NAME).exists()

    def test_missing_source_leaves_previous_snapshot_and_no_temp_files(
        self, tmp_path, build_helper, wal_source
    ):
        source, conn = wal_source
        dest_dir = tmp_path / "out"
        binary = build_helper(source, dest_dir)
        assert _run(binary).returncode == 0

        conn.close()
        for suffix in ("", "-wal", "-shm"):
            Path(f"{source}{suffix}").unlink(missing_ok=True)
        result = _run(binary)

        assert result.returncode == 1
        assert _rows(dest_dir / SNAPSHOT_NAME) == 50
        assert _leftover_temp_files(dest_dir) == []


BUILD_SCRIPT = SOURCE_FILE.parent / "build.sh"


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("relative/MoneyWiz.sqlite", "must be absolute"),
        ("/etc/passwd", "not a known MoneyWiz database location"),
        ("{home}/Library/Messages/chat.db", "not a known MoneyWiz database location"),
        (
            "{home}/Library/Containers/com.moneywiz.x/../../Messages/x.sqlite",
            "must not contain . or ..",
        ),
        ('{home}/Library/Containers/com.moneywiz.x/a"b.sqlite', "not supported"),
    ],
    ids=["relative", "system-file", "other-app", "dot-dot", "quote"],
)
def test_build_script_rejects_unsafe_source_paths(tmp_path, path, message):
    # The baked-in path is the only thing the privileged binary can read, so
    # build.sh must refuse anything outside known MoneyWiz locations.
    home = tmp_path / "home"
    home.mkdir()
    result = subprocess.run(
        ["/bin/bash", str(BUILD_SCRIPT), path.format(home=home)],
        capture_output=True,
        text=True,
        check=False,
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
    )

    assert result.returncode == 1
    assert message in result.stderr


def test_build_script_rejects_symlink_in_source_path(tmp_path):
    home = tmp_path / "home"
    real = home / "Library/Containers/com.moneywiz.real/Data"
    real.mkdir(parents=True)
    (real / "MoneyWiz.sqlite").write_bytes(b"")
    link = home / "Library/Containers/com.moneywiz.link"
    link.symlink_to(home / "Library/Containers/com.moneywiz.real")

    result = subprocess.run(
        ["/bin/bash", str(BUILD_SCRIPT), f"{link}/Data/MoneyWiz.sqlite"],
        capture_output=True,
        text=True,
        check=False,
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
    )

    assert result.returncode == 1
    assert "is a symlink" in result.stderr
