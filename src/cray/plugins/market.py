"""
Plugin marketplace for discovering and installing plugins.

Features:
- Search plugins from remote registry
- Install/uninstall plugins
- Plugin metadata and ratings
- Version management
"""

import json
import hashlib
import shutil
import subprocess
import sys
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from loguru import logger
import urllib.request
import urllib.error


@dataclass
class PluginInfo:
    """Information about a plugin."""
    name: str
    version: str
    description: str = ""
    author: str = ""
    homepage: str = ""
    repository: str = ""
    license: str = ""
    keywords: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    installed: bool = False
    installed_version: Optional[str] = None
    rating: float = 0.0
    downloads: int = 0
    actions: List[str] = field(default_factory=list)


@dataclass
class PluginManifest:
    """Plugin manifest file structure."""
    name: str
    version: str
    description: str = ""
    author: str = ""
    homepage: str = ""
    repository: str = ""
    license: str = "MIT"
    keywords: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    actions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginManifest":
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            homepage=data.get("homepage", ""),
            repository=data.get("repository", ""),
            license=data.get("license", "MIT"),
            keywords=data.get("keywords", []),
            dependencies=data.get("dependencies", []),
            actions=data.get("actions", {}),
            config=data.get("config", {}),
        )

    @classmethod
    def from_file(cls, path: Path) -> "PluginManifest":
        """Load manifest from file."""
        if not path.exists():
            raise FileNotFoundError(f"Manifest not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls.from_dict(data)

    def validate(self) -> List[str]:
        """Validate manifest fields, return list of errors."""
        errors = []
        if not self.name:
            errors.append("Manifest 'name' is empty")
        if not self.version:
            errors.append("Manifest 'version' is empty")
        # Validate version format (semver-like: X.Y.Z or X.Y)
        import re
        if self.version and not re.match(r"^\d+\.\d+(\.\d+)?", self.version):
            errors.append(f"Manifest 'version' '{self.version}' is not valid semver (e.g. 1.0.0)")
        return errors


class PluginRegistry:
    """
    Remote plugin registry client.
    
    Supports multiple registry sources:
    - Official Cray plugin registry
    - GitHub repositories
    - Local directories
    """

    DEFAULT_REGISTRY_URL = "https://cray-plugins.example.com/api/v1"
    GITHUB_RAW_URL = "https://raw.githubusercontent.com"

    def __init__(self, registry_url: Optional[str] = None):
        self.registry_url = registry_url or self.DEFAULT_REGISTRY_URL
        self._cache: Dict[str, PluginInfo] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = 300  # 5 minutes

    def _fetch_url(self, url: str) -> Optional[str]:
        """Fetch content from URL."""
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": f"Cray-Plugin-Market/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read().decode("utf-8")
        except urllib.error.URLError as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def search(
        self,
        query: str = "",
        keywords: List[str] = None,
        limit: int = 20
    ) -> List[PluginInfo]:
        """
        Search for plugins in the registry.
        
        Args:
            query: Search query
            keywords: Filter by keywords
            limit: Maximum results to return
            
        Returns:
            List of matching plugins
        """
        # For demo, return mock data
        # In production, this would query the actual registry
        mock_plugins = self._get_mock_plugins()

        results = []
        for plugin in mock_plugins:
            # Match query
            if query:
                query_lower = query.lower()
                if query_lower not in plugin.name.lower():
                    if query_lower not in plugin.description.lower():
                        if query_lower not in plugin.keywords:
                            continue

            # Match keywords
            if keywords:
                if not any(kw in plugin.keywords for kw in keywords):
                    continue

            results.append(plugin)

        return results[:limit]

    def get_plugin_info(self, name: str) -> Optional[PluginInfo]:
        """Get detailed info about a plugin."""
        plugins = self._get_mock_plugins()
        for plugin in plugins:
            if plugin.name == name:
                return plugin
        return None

    def get_plugin_manifest(self, name: str, version: str = "latest") -> Optional[PluginManifest]:
        """Get plugin manifest from registry."""
        # In production, fetch from actual registry
        return None

    def _get_mock_plugins(self) -> List[PluginInfo]:
        """Get mock plugin data for demo."""
        return [
            PluginInfo(
                name="aws",
                version="1.2.0",
                description="AWS cloud services integration - S3, EC2, Lambda, and more",
                author="Cray Team",
                keywords=["aws", "cloud", "s3", "ec2", "lambda"],
                rating=4.8,
                downloads=15234,
                actions=["s3_upload", "s3_download", "ec2_start", "lambda_invoke"]
            ),
            PluginInfo(
                name="slack",
                version="2.0.1",
                description="Send messages and notifications to Slack channels",
                author="Cray Team",
                keywords=["slack", "notification", "messaging"],
                rating=4.5,
                downloads=8921,
                actions=["send_message", "upload_file", "create_channel"]
            ),
            PluginInfo(
                name="database",
                version="1.5.0",
                description="Database operations for PostgreSQL, MySQL, SQLite",
                author="Cray Team",
                keywords=["database", "sql", "postgres", "mysql", "sqlite"],
                rating=4.7,
                downloads=12456,
                actions=["query", "insert", "update", "delete", "transaction"]
            ),
            PluginInfo(
                name="git",
                version="1.0.0",
                description="Git operations - clone, commit, push, pull, branch",
                author="Cray Team",
                keywords=["git", "version control", "github"],
                rating=4.3,
                downloads=5678,
                actions=["clone", "commit", "push", "pull", "branch", "merge"]
            ),
            PluginInfo(
                name="ai",
                version="0.9.0",
                description="AI/ML integrations - OpenAI, Anthropic, local models",
                author="Cray Team",
                keywords=["ai", "ml", "openai", "anthropic", "llm"],
                rating=4.9,
                downloads=23456,
                actions=["chat", "complete", "embed", "transcribe"]
            ),
            PluginInfo(
                name="pdf",
                version="1.1.0",
                description="PDF generation and manipulation",
                author="Cray Team",
                keywords=["pdf", "document", "report"],
                rating=4.2,
                downloads=7890,
                actions=["create", "merge", "split", "extract_text", "add_watermark"]
            ),
            PluginInfo(
                name="image",
                version="1.3.0",
                description="Image processing - resize, convert, compress, watermark",
                author="Cray Team",
                keywords=["image", "resize", "convert", "compress"],
                rating=4.4,
                downloads=9876,
                actions=["resize", "convert", "compress", "watermark", "metadata"]
            ),
            PluginInfo(
                name="crypto",
                version="1.0.0",
                description="Cryptographic operations - encrypt, decrypt, hash, sign",
                author="Cray Team",
                keywords=["crypto", "encrypt", "decrypt", "hash", "sign"],
                rating=4.6,
                downloads=4567,
                actions=["encrypt", "decrypt", "hash", "sign", "verify"]
            ),
            PluginInfo(
                name="redis",
                version="1.2.0",
                description="Redis cache and message queue operations",
                author="Cray Team",
                keywords=["redis", "cache", "queue", "pubsub"],
                rating=4.5,
                downloads=6789,
                actions=["get", "set", "delete", "publish", "subscribe"]
            ),
            PluginInfo(
                name="kubernetes",
                version="0.8.0",
                description="Kubernetes cluster management and deployments",
                author="Cray Team",
                keywords=["kubernetes", "k8s", "container", "deployment"],
                rating=4.1,
                downloads=3456,
                actions=["deploy", "scale", "logs", "exec", "port_forward"]
            ),
        ]


class PluginMarket:
    """
    Plugin marketplace for managing plugins.

    Features:
    - Search and discover plugins
    - Install/uninstall plugins
    - Update plugins
    - List installed plugins

    Security:
    - By default, arbitrary pip dependencies are blocked.
    - Set allow_arbitrary_deps=True to allow (not recommended).
    - When allow_arbitrary_deps=False, --no-deps is used for pip install
      to prevent transitive arbitrary package installs.
    """

    # Known safe packages commonly used by plugins
    _SAFE_PACKAGES = {
        "requests", "aiohttp", "httpx", "redis", "boto3",
        "pandas", "numpy", "jinja2", "pyyaml", "toml",
        "python-dateutil", "pytz", "click", "rich",
    }

    def __init__(
        self,
        plugin_dir: Optional[Path] = None,
        registry: Optional[PluginRegistry] = None,
        allow_arbitrary_deps: bool = False,
    ):
        self.plugin_dir = plugin_dir or Path.home() / ".cray" / "plugins"
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        self.registry = registry or PluginRegistry()
        self._installed_cache: Optional[Dict[str, PluginManifest]] = None
        self._allow_arbitrary_deps = allow_arbitrary_deps

    @staticmethod
    def _is_safe_dependency(dep_spec: str) -> bool:
        """Check if a dependency spec is safe to install.

        Only allows known-safe package names without extras or URLs.
        """
        # Extract package name (before version specifiers)
        import re
        match = re.match(r'^([a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?)', dep_spec)
        if not match:
            return False
        pkg_name = match.group(1).lower().replace("-", "_")
        # Block URL-based installs
        if "://" in dep_spec or "@" in dep_spec:
            return False
        # Block local file installs
        if dep_spec.startswith(".") or dep_spec.startswith("/"):
            return False
        return pkg_name in PluginMarket._SAFE_PACKAGES

    @staticmethod
    def _compute_package_hash(plugin_path: Path) -> str:
        """Compute SHA-256 hash of all files in a plugin package.

        Returns hex digest of the combined file hashes, sorted by path
        for deterministic output.
        """
        file_hashes = []
        for fp in sorted(plugin_path.rglob("*")):
            if fp.is_file() and fp.name != "package.hash":
                rel = fp.relative_to(plugin_path)
                content = fp.read_bytes()
                h = hashlib.sha256(content).hexdigest()
                file_hashes.append(f"{rel}:{h}")
        combined = "\n".join(file_hashes)
        return hashlib.sha256(combined.encode()).hexdigest()

    def _verify_package(self, plugin_path: Path, expected_hash: Optional[str] = None) -> List[str]:
        """Verify an installed plugin package integrity.

        Checks:
        - manifest.json exists and is valid
        - plugin.py exists
        - No unexpected executable files (.sh, .bat, .cmd, .ps1)
        - If expected_hash provided, verify it matches

        Returns list of verification errors (empty = valid).
        """
        errors = []

        # Check required files
        manifest_path = plugin_path / "manifest.json"
        if not manifest_path.exists():
            errors.append(f"Missing manifest.json in {plugin_path.name}")
        else:
            try:
                manifest = PluginManifest.from_file(manifest_path)
                manifest_errors = manifest.validate()
                errors.extend(manifest_errors)
            except Exception as e:
                errors.append(f"Invalid manifest.json: {e}")

        plugin_py = plugin_path / "plugin.py"
        if not plugin_py.exists():
            errors.append(f"Missing plugin.py in {plugin_path.name}")

        # Check for dangerous executable files
        dangerous_extensions = {".sh", ".bat", ".cmd", ".ps1", ".exe", ".dll", ".so"}
        for fp in plugin_path.rglob("*"):
            if fp.is_file() and fp.suffix.lower() in dangerous_extensions:
                errors.append(
                    f"Suspicious file found: {fp.relative_to(plugin_path)}. "
                    f"Plugins should not contain executable files."
                )

        # Verify package hash if provided
        if expected_hash is not None:
            actual_hash = self._compute_package_hash(plugin_path)
            if actual_hash != expected_hash:
                errors.append(
                    f"Package hash mismatch: expected {expected_hash[:16]}... "
                    f"got {actual_hash[:16]}..."
                )

        return errors

    def search(
        self,
        query: str = "",
        keywords: List[str] = None,
        limit: int = 20
    ) -> List[PluginInfo]:
        """Search for plugins."""
        plugins = self.registry.search(query, keywords, limit)
        
        # Mark installed plugins
        installed = self.list_installed()
        for plugin in plugins:
            if plugin.name in installed:
                plugin.installed = True
                plugin.installed_version = installed[plugin.name].version

        return plugins

    def get_info(self, name: str) -> Optional[PluginInfo]:
        """Get plugin info."""
        plugin = self.registry.get_plugin_info(name)
        if plugin:
            installed = self.list_installed()
            if name in installed:
                plugin.installed = True
                plugin.installed_version = installed[name].version
        return plugin

    def install(
        self,
        name: str,
        version: Optional[str] = None,
        force: bool = False
    ) -> bool:
        """
        Install a plugin.
        
        Args:
            name: Plugin name
            version: Specific version (optional)
            force: Force reinstall if already installed
            
        Returns:
            True if installation successful
        """
        # Check if already installed
        installed = self.list_installed()
        if name in installed and not force:
            logger.info(f"Plugin '{name}' already installed (version {installed[name].version})")
            return True

        # Get plugin info
        info = self.registry.get_plugin_info(name)
        if not info:
            logger.error(f"Plugin '{name}' not found in registry")
            return False

        # Create plugin directory
        plugin_path = self.plugin_dir / name
        if plugin_path.exists() and force:
            shutil.rmtree(plugin_path)
        
        plugin_path.mkdir(parents=True, exist_ok=True)

        # Install dependencies — with safety checks
        if info.dependencies:
            if not self._allow_arbitrary_deps:
                # Only allow deps that match known safe patterns
                blocked = [d for d in info.dependencies if not self._is_safe_dependency(d)]
                if blocked:
                    raise ValueError(
                        f"Plugin '{name}' has blocked dependencies: {blocked}. "
                        f"Set allow_arbitrary_deps=True in config to allow."
                    )
            logger.info(f"Installing dependencies for '{name}'...")
            for dep in info.dependencies:
                try:
                    # Use --no-deps to prevent transitive arbitrary installs
                    # unless explicitly allowed
                    cmd = [sys.executable, "-m", "pip", "install"]
                    if not self._allow_arbitrary_deps:
                        cmd.append("--no-deps")
                    cmd.append(dep)
                    subprocess.run(cmd, check=True, capture_output=True)
                    logger.debug(f"Installed dependency: {dep}")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Failed to install dependency {dep}: {e}")

        # Create plugin manifest
        manifest = PluginManifest(
            name=name,
            version=version or info.version,
            description=info.description,
            author=info.author,
            keywords=info.keywords,
            dependencies=info.dependencies,
        )

        manifest_path = plugin_path / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2)

        # Create plugin stub file
        self._create_plugin_stub(plugin_path, manifest)

        # Verify installed package integrity
        verify_errors = self._verify_package(plugin_path)
        if verify_errors:
            logger.warning(
                f"Package verification issues for '{name}': {verify_errors}"
            )

        # Save package hash for future integrity checks
        package_hash = self._compute_package_hash(plugin_path)
        hash_path = plugin_path / "package.hash"
        with open(hash_path, "w", encoding="utf-8") as f:
            f.write(package_hash)

        # Invalidate cache
        self._installed_cache = None

        logger.success(f"Plugin '{name}' v{manifest.version} installed successfully")
        return True

    def _create_plugin_stub(self, plugin_path: Path, manifest: PluginManifest) -> None:
        """Create a plugin stub file."""
        stub_code = f'''"""
{manifest.name} - {manifest.description}
"""

from typing import Dict, Any
from cray.plugins import Plugin


class {manifest.name.capitalize()}Plugin(Plugin):
    """Auto-generated plugin stub."""

    name = "{manifest.name}"
    description = """{manifest.description}"""
    version = "{manifest.version}"

    async def execute(
        self,
        action: str,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Any:
        """Execute an action."""
        # TODO: Implement plugin actions
        raise NotImplementedError(f"Action '{{action}}' not implemented")


# Plugin registration
plugin = {manifest.name.capitalize()}Plugin
'''

        stub_path = plugin_path / "plugin.py"
        with open(stub_path, "w", encoding="utf-8") as f:
            f.write(stub_code)

    def uninstall(self, name: str) -> bool:
        """Uninstall a plugin."""
        plugin_path = self.plugin_dir / name
        
        if not plugin_path.exists():
            logger.warning(f"Plugin '{name}' is not installed")
            return False

        try:
            shutil.rmtree(plugin_path)
            self._installed_cache = None
            logger.success(f"Plugin '{name}' uninstalled")
            return True
        except Exception as e:
            logger.error(f"Failed to uninstall '{name}': {e}")
            return False

    def update(self, name: str) -> bool:
        """Update a plugin to latest version."""
        info = self.registry.get_plugin_info(name)
        if not info:
            logger.error(f"Plugin '{name}' not found")
            return False

        installed = self.list_installed()
        if name not in installed:
            logger.warning(f"Plugin '{name}' is not installed")
            return self.install(name)

        current_version = installed[name].version
        if current_version == info.version:
            logger.info(f"Plugin '{name}' is already up to date (v{current_version})")
            return True

        logger.info(f"Updating '{name}' from v{current_version} to v{info.version}")
        return self.install(name, force=True)

    def update_all(self) -> Dict[str, bool]:
        """Update all installed plugins."""
        results = {}
        for name in self.list_installed():
            results[name] = self.update(name)
        return results

    def list_installed(self) -> Dict[str, PluginManifest]:
        """List all installed plugins."""
        if self._installed_cache:
            return self._installed_cache

        installed = {}

        if not self.plugin_dir.exists():
            return installed

        for plugin_path in self.plugin_dir.iterdir():
            if plugin_path.is_dir():
                manifest_path = plugin_path / "manifest.json"
                if manifest_path.exists():
                    try:
                        manifest = PluginManifest.from_file(manifest_path)
                        # Validate manifest fields
                        manifest_errors = manifest.validate()
                        if manifest_errors:
                            logger.warning(
                                f"Invalid manifest for {plugin_path.name}: {manifest_errors}"
                            )
                            continue
                        # Verify package integrity if hash exists
                        hash_path = plugin_path / "package.hash"
                        if hash_path.exists():
                            expected_hash = hash_path.read_text(encoding="utf-8").strip()
                            verify_errors = self._verify_package(
                                plugin_path, expected_hash=expected_hash
                            )
                            if verify_errors:
                                logger.warning(
                                    f"Integrity check failed for {plugin_path.name}: {verify_errors}"
                                )
                                continue
                        installed[manifest.name] = manifest
                    except Exception as e:
                        logger.warning(f"Failed to load manifest for {plugin_path.name}: {e}")

        self._installed_cache = installed
        return installed

    def get_plugin_path(self, name: str) -> Optional[Path]:
        """Get the path to an installed plugin."""
        plugin_path = self.plugin_dir / name
        if plugin_path.exists():
            return plugin_path
        return None
