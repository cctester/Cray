"""
Tests for the plugin marketplace.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from cray.plugins.market import (
    PluginMarket,
    PluginRegistry,
    PluginInfo,
    PluginManifest,
)


class TestPluginInfo:
    """Tests for PluginInfo dataclass."""

    def test_create_plugin_info(self):
        """Test creating plugin info."""
        info = PluginInfo(
            name="test-plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author",
            rating=4.5,
            downloads=1000,
        )

        assert info.name == "test-plugin"
        assert info.version == "1.0.0"
        assert info.installed is False

    def test_plugin_info_defaults(self):
        """Test plugin info defaults."""
        info = PluginInfo(name="test", version="1.0")

        assert info.description == ""
        assert info.keywords == []
        assert info.dependencies == []
        assert info.actions == []


class TestPluginManifest:
    """Tests for PluginManifest."""

    def test_create_manifest(self):
        """Test creating a manifest."""
        manifest = PluginManifest(
            name="test",
            version="1.0.0",
            description="Test plugin",
            actions={"run": {"params": {}}}
        )

        assert manifest.name == "test"
        assert manifest.actions == {"run": {"params": {}}}

    def test_manifest_to_dict(self):
        """Test converting manifest to dict."""
        manifest = PluginManifest(
            name="test",
            version="1.0.0",
            keywords=["test", "plugin"]
        )

        data = manifest.to_dict()
        assert data["name"] == "test"
        assert data["keywords"] == ["test", "plugin"]

    def test_manifest_from_dict(self):
        """Test creating manifest from dict."""
        data = {
            "name": "test",
            "version": "2.0.0",
            "description": "Test",
            "keywords": ["a", "b"]
        }

        manifest = PluginManifest.from_dict(data)
        assert manifest.name == "test"
        assert manifest.version == "2.0.0"
        assert manifest.keywords == ["a", "b"]

    def test_manifest_file_roundtrip(self):
        """Test saving and loading manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.json"

            original = PluginManifest(
                name="test",
                version="1.5.0",
                description="Test plugin",
                author="Test Author",
                keywords=["test"],
                dependencies=["requests"]
            )

            # Save
            with open(manifest_path, "w") as f:
                import json
                json.dump(original.to_dict(), f)

            # Load
            loaded = PluginManifest.from_file(manifest_path)

            assert loaded.name == original.name
            assert loaded.version == original.version
            assert loaded.description == original.description
            assert loaded.keywords == original.keywords


class TestPluginRegistry:
    """Tests for PluginRegistry."""

    def test_search_all(self):
        """Test searching all plugins."""
        registry = PluginRegistry()
        plugins = registry.search()

        assert len(plugins) > 0
        assert all(isinstance(p, PluginInfo) for p in plugins)

    def test_search_with_query(self):
        """Test searching with query."""
        registry = PluginRegistry()
        plugins = registry.search(query="aws")

        assert len(plugins) > 0
        assert any("aws" in p.name.lower() for p in plugins)

    def test_search_with_keywords(self):
        """Test searching with keywords."""
        registry = PluginRegistry()
        plugins = registry.search(keywords=["database"])

        assert len(plugins) > 0
        assert any("database" in p.keywords for p in plugins)

    def test_get_plugin_info(self):
        """Test getting plugin info."""
        registry = PluginRegistry()
        info = registry.get_plugin_info("aws")

        assert info is not None
        assert info.name == "aws"

    def test_get_nonexistent_plugin(self):
        """Test getting nonexistent plugin."""
        registry = PluginRegistry()
        info = registry.get_plugin_info("nonexistent-plugin-xyz")

        assert info is None


class TestPluginMarket:
    """Tests for PluginMarket."""

    def test_search(self):
        """Test market search."""
        with tempfile.TemporaryDirectory() as tmpdir:
            market = PluginMarket(plugin_dir=Path(tmpdir))
            plugins = market.search("slack")

            assert len(plugins) > 0
            assert plugins[0].name == "slack"

    def test_install_and_uninstall(self):
        """Test installing and uninstalling a plugin."""
        with tempfile.TemporaryDirectory() as tmpdir:
            market = PluginMarket(plugin_dir=Path(tmpdir))

            # Install
            result = market.install("redis")
            assert result is True

            # Check installed
            installed = market.list_installed()
            assert "redis" in installed

            # Uninstall
            result = market.uninstall("redis")
            assert result is True

            # Check uninstalled
            installed = market.list_installed()
            assert "redis" not in installed

    def test_install_creates_files(self):
        """Test that install creates plugin files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir)
            market = PluginMarket(plugin_dir=plugin_dir)

            market.install("git")

            plugin_path = plugin_dir / "git"
            assert plugin_path.exists()
            assert (plugin_path / "manifest.json").exists()
            assert (plugin_path / "plugin.py").exists()

    def test_list_installed_empty(self):
        """Test listing when no plugins installed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            market = PluginMarket(plugin_dir=Path(tmpdir))
            installed = market.list_installed()

            assert installed == {}

    def test_get_plugin_path(self):
        """Test getting plugin path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir)
            market = PluginMarket(plugin_dir=plugin_dir)

            # Not installed
            path = market.get_plugin_path("nonexistent")
            assert path is None

            # Install and get path
            market.install("slack")
            path = market.get_plugin_path("slack")
            assert path is not None
            assert path.name == "slack"

    def test_reinstall_with_force(self):
        """Test reinstalling with force flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            market = PluginMarket(plugin_dir=Path(tmpdir))

            # Install
            market.install("aws")

            # Try install again without force (should succeed, already installed)
            result = market.install("aws", force=False)
            assert result is True

            # Force reinstall
            result = market.install("aws", force=True)
            assert result is True

    def test_get_info_marks_installed(self):
        """Test that get_info marks installed plugins."""
        with tempfile.TemporaryDirectory() as tmpdir:
            market = PluginMarket(plugin_dir=Path(tmpdir))

            # Before install
            info = market.get_info("database")
            assert info.installed is False

            # Install
            market.install("database")

            # After install
            info = market.get_info("database")
            assert info.installed is True
            assert info.installed_version is not None

    def test_install_creates_package_hash(self):
        """Test that install creates a package.hash file (#5)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir)
            market = PluginMarket(plugin_dir=plugin_dir)

            market.install("redis")

            hash_path = plugin_dir / "redis" / "package.hash"
            assert hash_path.exists()
            hash_content = hash_path.read_text().strip()
            assert len(hash_content) == 64  # SHA-256 hex digest

    def test_verify_package_valid(self):
        """Test package verification on valid plugin (#5)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir)
            market = PluginMarket(plugin_dir=plugin_dir)

            market.install("git")

            plugin_path = plugin_dir / "git"
            errors = market._verify_package(plugin_path)
            assert errors == []

    def test_verify_package_missing_manifest(self):
        """Test package verification detects missing manifest (#5)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir)
            market = PluginMarket(plugin_dir=plugin_dir)

            # Create a plugin dir without manifest
            bad_plugin = plugin_dir / "bad-plugin"
            bad_plugin.mkdir()
            (bad_plugin / "plugin.py").write_text("# stub")

            errors = market._verify_package(bad_plugin)
            assert any("manifest" in e.lower() for e in errors)

    def test_verify_package_suspicious_files(self):
        """Test package verification detects suspicious executable files (#5)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir)
            market = PluginMarket(plugin_dir=plugin_dir)

            market.install("aws")

            # Add a suspicious .sh file
            plugin_path = plugin_dir / "aws"
            (plugin_path / "malicious.sh").write_text("#!/bin/bash\nevil")

            errors = market._verify_package(plugin_path)
            assert any("suspicious" in e.lower() for e in errors)

    def test_verify_package_hash_mismatch(self):
        """Test package verification detects hash mismatch (#5)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir)
            market = PluginMarket(plugin_dir=plugin_dir)

            market.install("slack")

            # Tamper with a file
            plugin_path = plugin_dir / "slack"
            (plugin_path / "plugin.py").write_text("# tampered")

            # Use the original hash (which won't match anymore)
            fake_hash = "0" * 64
            errors = market._verify_package(plugin_path, expected_hash=fake_hash)
            assert any("hash mismatch" in e.lower() for e in errors)

    def test_list_installed_skips_invalid_manifest(self):
        """Test that list_installed skips plugins with invalid manifests (#5)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir)
            market = PluginMarket(plugin_dir=plugin_dir)

            # Install a valid plugin
            market.install("redis")

            # Create a plugin with empty name in manifest
            bad_dir = plugin_dir / "bad-plugin"
            bad_dir.mkdir()
            import json
            bad_manifest = {"name": "", "version": ""}
            (bad_dir / "manifest.json").write_text(json.dumps(bad_manifest))
            (bad_dir / "plugin.py").write_text("# stub")

            installed = market.list_installed()
            assert "redis" in installed
            assert "bad-plugin" not in installed
            assert "" not in installed

    def test_manifest_validate(self):
        """Test PluginManifest.validate() (#5)."""
        # Valid manifest
        good = PluginManifest(name="test", version="1.0.0")
        assert good.validate() == []

        # Empty name
        bad1 = PluginManifest(name="", version="1.0.0")
        errors = bad1.validate()
        assert any("name" in e.lower() for e in errors)

        # Empty version
        bad2 = PluginManifest(name="test", version="")
        errors = bad2.validate()
        assert any("version" in e.lower() for e in errors)

        # Bad version format
        bad3 = PluginManifest(name="test", version="abc")
        errors = bad3.validate()
        assert any("version" in e.lower() and "semver" in e.lower() for e in errors)


class TestPluginMarketIntegration:
    """Integration tests for plugin market."""

    def test_full_workflow(self):
        """Test full plugin workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            market = PluginMarket(plugin_dir=Path(tmpdir))

            # Search
            plugins = market.search("ai")
            assert len(plugins) > 0

            # Get info
            info = market.get_info("ai")
            assert info is not None

            # Install
            assert market.install("ai") is True

            # List installed
            installed = market.list_installed()
            assert "ai" in installed

            # Uninstall
            assert market.uninstall("ai") is True

            # Verify uninstalled
            installed = market.list_installed()
            assert "ai" not in installed
