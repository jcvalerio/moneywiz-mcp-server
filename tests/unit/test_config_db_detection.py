"""Unit tests for MoneyWiz database auto-detection."""

from unittest.mock import patch

import pytest

from moneywiz_mcp_server.config import Config


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
