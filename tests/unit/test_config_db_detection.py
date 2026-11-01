"""Unit tests for MoneyWiz database auto-detection."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

from moneywiz_mcp_server.config import Config, find_moneywiz_databases


class TestFindMoneyWizDatabase:
    """Test cases for Config._find_moneywiz_database."""

    @pytest.mark.unit
    def test_finds_icloud_sync_database_under_application_support(self, tmp_path):
        app_support = (
            tmp_path
            / "Library/Containers/com.moneywiz.personalfinance/Data/Library/Application Support"
        )
        app_support.mkdir(parents=True)
        db_file = app_support / "MoneyWiz_iCloud.sqlite"
        db_file.write_bytes(b"sqlite data")

        with patch("moneywiz_mcp_server.config.Path.home", return_value=tmp_path):
            found = Config._find_moneywiz_database()

        assert found == str(db_file)

    @pytest.mark.unit
    def test_finds_legacy_documents_database_when_no_icloud_sync(self, tmp_path):
        documents = (
            tmp_path / "Library/Containers/com.moneywiz.personalfinance/Data/Documents"
        )
        documents.mkdir(parents=True)
        db_file = documents / "ipadMoneyWiz.sqlite"
        db_file.write_bytes(b"sqlite data")

        with patch("moneywiz_mcp_server.config.Path.home", return_value=tmp_path):
            found = Config._find_moneywiz_database()

        assert found == str(db_file)

    @pytest.mark.unit
    def test_skips_cloudkit_shared_store(self, tmp_path):
        app_support = (
            tmp_path
            / "Library/Containers/com.moneywiz.personalfinance/Data/Library/Application Support"
        )
        app_support.mkdir(parents=True)
        shared = app_support / "MoneyWiz_iCloud_shared.sqlite"
        shared.write_bytes(b"sqlite data")
        db_file = app_support / "MoneyWiz_iCloud.sqlite"
        db_file.write_bytes(b"sqlite data")

        with patch("moneywiz_mcp_server.config.Path.home", return_value=tmp_path):
            found = Config._find_moneywiz_database()

        assert found == str(db_file)

    @pytest.mark.unit
    def test_returns_none_when_only_shared_store_present(self, tmp_path):
        app_support = (
            tmp_path
            / "Library/Containers/com.moneywiz.personalfinance/Data/Library/Application Support"
        )
        app_support.mkdir(parents=True)
        (app_support / "MoneyWiz_iCloud_shared.sqlite").write_bytes(b"sqlite data")

        with patch("moneywiz_mcp_server.config.Path.home", return_value=tmp_path):
            found = Config._find_moneywiz_database()

        assert found is None

    @pytest.mark.unit
    def test_returns_none_when_no_database_found(self, tmp_path):
        with patch("moneywiz_mcp_server.config.Path.home", return_value=tmp_path):
            found = Config._find_moneywiz_database()

        assert found is None


APP_SUPPORT = (
    "Library/Containers/com.moneywiz.personalfinance/Data/Library/Application Support"
)
DOCUMENTS = "Library/Containers/com.moneywiz.personalfinance/Data/Documents"


def _make(root, relative_dir, name, content=b"sqlite data"):
    directory = root / relative_dir
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(content)
    return path


class TestFindMoneyWizDatabases:
    """Test cases for find_moneywiz_databases candidate ranking and filtering."""

    @pytest.mark.unit
    def test_prefers_application_support_over_documents(self, tmp_path):
        legacy = _make(tmp_path, DOCUMENTS, "ipadMoneyWiz.sqlite")
        current = _make(tmp_path, APP_SUPPORT, "MoneyWiz_iCloud.sqlite")

        assert find_moneywiz_databases(tmp_path) == [current, legacy]

    @pytest.mark.unit
    def test_shared_store_in_preferred_dir_does_not_shadow_real_database(
        self, tmp_path
    ):
        # Without the shared-store exclusion this would win on directory order
        _make(tmp_path, APP_SUPPORT, "MoneyWiz_iCloud_shared.sqlite")
        legacy = _make(tmp_path, DOCUMENTS, "ipadMoneyWiz.sqlite")

        assert find_moneywiz_databases(tmp_path) == [legacy]

    @pytest.mark.unit
    def test_ignores_sqlite_side_files(self, tmp_path):
        for name in (
            "MoneyWiz_iCloud_shared.sqlite-wal",
            "MoneyWiz_iCloud_shared.sqlite-shm",
            "MoneyWiz_iCloud.sqlite-wal",
            "MoneyWiz_iCloud.sqlite-journal",
        ):
            _make(tmp_path, APP_SUPPORT, name)

        assert find_moneywiz_databases(tmp_path) == []

    @pytest.mark.unit
    def test_moneywiz_named_file_beats_unrelated_store(self, tmp_path):
        # "Analytics" sorts before "MoneyWiz", so name order alone would pick it
        _make(tmp_path, APP_SUPPORT, "Analytics.sqlite")
        real = _make(tmp_path, APP_SUPPORT, "MoneyWiz_iCloud.sqlite")

        assert find_moneywiz_databases(tmp_path)[0] == real

    @pytest.mark.unit
    def test_moneywiz_name_outranks_directory_preference(self, tmp_path):
        _make(tmp_path, APP_SUPPORT, "Analytics.sqlite")
        legacy = _make(tmp_path, DOCUMENTS, "ipadMoneyWiz.sqlite")

        assert find_moneywiz_databases(tmp_path)[0] == legacy

    @pytest.mark.unit
    def test_name_match_is_case_insensitive(self, tmp_path):
        _make(tmp_path, APP_SUPPORT, "Analytics.sqlite")
        lower = _make(tmp_path, APP_SUPPORT, "moneywiz.db")

        assert find_moneywiz_databases(tmp_path)[0] == lower

    @pytest.mark.unit
    def test_falls_back_to_generic_sqlite_name(self, tmp_path):
        generic = _make(tmp_path, "Library/Application Support/MoneyWiz", "data.sqlite")

        assert find_moneywiz_databases(tmp_path) == [generic]

    @pytest.mark.unit
    def test_skips_empty_files_and_directories(self, tmp_path):
        _make(tmp_path, APP_SUPPORT, "MoneyWiz_iCloud.sqlite", content=b"")
        (tmp_path / APP_SUPPORT / "Store.sqlite").mkdir()

        assert find_moneywiz_databases(tmp_path) == []

    @pytest.mark.unit
    def test_unreadable_directory_is_skipped_with_warning(self, tmp_path, caplog):
        _make(tmp_path, APP_SUPPORT, "MoneyWiz_iCloud.sqlite")
        legacy = _make(tmp_path, DOCUMENTS, "ipadMoneyWiz.sqlite")
        blocked = tmp_path / APP_SUPPORT
        real_iterdir = Path.iterdir

        def fake_iterdir(self):
            if self == blocked:
                raise PermissionError(1, "Operation not permitted")
            return real_iterdir(self)

        with patch.object(Path, "iterdir", fake_iterdir):
            found = find_moneywiz_databases(tmp_path)

        assert found == [legacy]
        assert "Cannot read" in caplog.text

    @pytest.mark.unit
    def test_setup_env_uses_same_detection(self, tmp_path, request):
        _make(tmp_path, APP_SUPPORT, "MoneyWiz_iCloud_shared.sqlite")
        real = _make(tmp_path, APP_SUPPORT, "MoneyWiz_iCloud.sqlite")
        script = request.config.rootpath / "setup_env.py"
        assert script.is_file(), f"setup_env.py not found at {script}"
        spec = importlib.util.spec_from_file_location("setup_env", script)
        assert spec is not None
        assert spec.loader is not None
        setup_env = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup_env)

        with patch("moneywiz_mcp_server.config.Path.home", return_value=tmp_path):
            assert setup_env.find_moneywiz_database() == [real]
