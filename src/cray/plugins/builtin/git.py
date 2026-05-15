"""
Git plugin for repository operations.

Supports:
- Clone, pull, push
- Commit, add, rm
- Branch management
- Tag management
- Status, log, diff
"""

import asyncio
import os
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from loguru import logger

from cray.plugins import Plugin

# --- Input validation helpers (#24: prevent command injection) ---

# Git ref names: alphanumeric, dot, dash, underscore, slash
_REF_RE = re.compile(r'^[a-zA-Z0-9._\-/]+$')

# Git config keys: sections separated by dots, alphanumeric + dash
_CONFIG_KEY_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9\-]*(?:\.[a-zA-Z][a-zA-Z0-9\-]*)+$')

# Git config values: printable ASCII, no newlines
_CONFIG_VALUE_RE = re.compile(r'^[^\n\r]+$')

# Allowed git log format specifiers (safe subset)
_SAFE_FORMAT_RE = re.compile(r'^[%a-zA-Z0-9\s|,.\-_:()]+$')

# Allowed reset modes
_RESET_MODES = {"soft", "mixed", "hard", "merge"}

# Allowed stash actions
_STASH_ACTIONS = {"push", "pop", "list", "drop", "apply"}

# Allowed branch/tag actions
_REF_ACTIONS = {"list", "create", "delete"}

# Allowed remote actions
_REMOTE_ACTIONS = {"list", "add", "remove", "get_url"}

# Allowed config actions
_CONFIG_ACTIONS = {"get", "set", "list"}


def _validate_ref(value: str, name: str = "ref") -> str:
    """Validate a git ref name (branch, tag, remote name, etc.)."""
    if not value:
        raise ValueError(f"{name} must not be empty")
    if not _REF_RE.match(value):
        raise ValueError(
            f"Invalid {name}: {value!r}. "
            "Only alphanumeric, dot, dash, underscore, and slash allowed."
        )
    # Reject path traversal and dash-prefixed refs (could be flags)
    if ".." in value or value.startswith("/") or value.startswith("-"):
        raise ValueError(f"Invalid {name}: {value!r} (path traversal or dash prefix)")
    return value


def _validate_commit_hash(value: str) -> str:
    """Validate a commit hash or ref expression."""
    if not value:
        raise ValueError("Commit reference must not be empty")
    # Allow hex hashes (7-40 chars)
    if re.match(r'^[a-fA-F0-9]{7,40}$', value):
        return value
    # Allow HEAD, HEAD~N, HEAD^N style
    if re.match(r'^HEAD[~^]\d+$', value):
        return value
    # Otherwise validate as a ref
    return _validate_ref(value, "commit reference")


def _validate_path(value: str, name: str = "path") -> str:
    """Validate a filesystem path to prevent traversal."""
    if not value:
        return value
    # Block path traversal
    if ".." in value:
        raise ValueError(f"Invalid {name}: path traversal not allowed")
    return value


class GitPlugin(Plugin):
    """Git repository operations."""

    name = "git"
    description = "Git repository operations (clone, commit, push, pull, branch, tag)"
    version = "1.0.0"
    
    @property
    def actions(self):
        return {
            "clone": {"description": "Clone repository", "params": [{"name": "url", "type": "string", "required": True, "description": "Repository URL"}, {"name": "path", "type": "string", "required": False, "description": "Target path"}]},
            "init": {"description": "Initialize repository", "params": [{"name": "path", "type": "string", "required": True, "description": "Repository path"}]},
            "status": {"description": "Get status", "params": [{"name": "path", "type": "string", "required": True, "description": "Repository path"}]},
            "add": {"description": "Stage files", "params": [{"name": "path", "type": "string", "required": True, "description": "Repository path"}, {"name": "files", "type": "array", "required": False, "description": "Files to stage"}]},
            "commit": {"description": "Create commit", "params": [{"name": "path", "type": "string", "required": True, "description": "Repository path"}, {"name": "message", "type": "string", "required": True, "description": "Commit message"}]},
            "push": {"description": "Push changes", "params": [{"name": "path", "type": "string", "required": True, "description": "Repository path"}]},
            "pull": {"description": "Pull changes", "params": [{"name": "path", "type": "string", "required": True, "description": "Repository path"}]},
            "branch": {"description": "Manage branches", "params": [{"name": "path", "type": "string", "required": True, "description": "Repository path"}, {"name": "name", "type": "string", "required": False, "description": "Branch name"}]},
        }
    
    async def execute(
        self,
        action: str,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Any:
        """Execute a git action."""

        actions = {
            "clone": self._clone,
            "init": self._init,
            "status": self._status,
            "add": self._add,
            "rm": self._rm,
            "commit": self._commit,
            "push": self._push,
            "pull": self._pull,
            "fetch": self._fetch,
            "branch": self._branch,
            "checkout": self._checkout,
            "merge": self._merge,
            "tag": self._tag,
            "log": self._log,
            "diff": self._diff,
            "remote": self._remote,
            "reset": self._reset,
            "stash": self._stash,
            "config": self._config,
        }

        if action not in actions:
            return {"error": f"Unknown action: {action}"}

        try:
            return await actions[action](params, context)
        except ValueError as e:
            logger.error(f"Git plugin validation error: {e}")
            return {"success": False, "error": str(e)}

    async def _run_git(
        self,
        args: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Run a git command.

        All user-provided values are passed as separate arguments to
        subprocess_exec (not shell=True) to prevent command injection.
        Input validation is performed in each action method before
        calling this method.
        """
        try:
            # Validate cwd to prevent path traversal
            if cwd:
                _validate_path(cwd, "cwd")

            # Validate env values — no newlines (prevent header injection)
            if env:
                for k, v in env.items():
                    if "\n" in v or "\r" in v:
                        raise ValueError(f"Invalid env value for {k}: contains newlines")

            # Merge environment
            cmd_env = os.environ.copy()
            if env:
                cmd_env.update(env)

            # Build command — each arg is passed separately, no shell injection possible
            cmd = ["git"] + args

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                env=cmd_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wait for completion
            stdout, stderr = await proc.communicate()

            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace").strip(),
                "stderr": stderr.decode("utf-8", errors="replace").strip(),
            }

        except ValueError as e:
            # Re-raise validation errors clearly
            logger.error(f"Git input validation failed: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Git command failed: {e}")
            return {"success": False, "error": str(e)}

    async def _clone(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Clone a repository.

        Params:
            url: Repository URL
            path: Destination path (optional)
            branch: Branch to clone (optional)
            depth: Shallow clone depth (optional)
            recursive: Clone submodules (default: false)
            single_branch: Clone single branch (optional)

        Returns:
            Clone result
        """
        url = params.get("url", "")
        path = params.get("path", ".")
        branch = params.get("branch")
        depth = params.get("depth")
        recursive = params.get("recursive", False)
        single_branch = params.get("single_branch", False)

        if not url:
            return {"success": False, "error": "Repository URL required"}

        # #24: Validate inputs
        _validate_path(path, "path")
        if branch:
            _validate_ref(branch, "branch")
        if depth is not None:
            try:
                int(depth)
            except (ValueError, TypeError):
                return {"success": False, "error": f"Invalid depth: {depth!r}"}

        args = ["clone"]

        if branch:
            args.extend(["--branch", branch])

        if depth:
            args.extend(["--depth", str(depth)])

        if single_branch:
            args.append("--single-branch")

        if recursive:
            args.append("--recursive")

        args.append(url)

        if path and path != ".":
            args.append(path)

        result = await self._run_git(args)

        if result["success"]:
            logger.info(f"Cloned {url} to {path}")
            return {
                "success": True,
                "url": url,
                "path": path or url.split("/")[-1].replace(".git", ""),
            }

        return result

    async def _init(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Initialize a new repository.

        Params:
            path: Repository path (default: current directory)
            bare: Create bare repository (optional)

        Returns:
            Init result
        """
        path = params.get("path", ".")
        bare = params.get("bare", False)

        # #24: Validate path
        _validate_path(path, "path")

        args = ["init"]
        if bare:
            args.append("--bare")

        result = await self._run_git(args, cwd=path)

        if result["success"]:
            logger.info(f"Initialized repository at {path}")
            return {"success": True, "path": path, "bare": bare}

        return result

    async def _status(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get repository status.

        Params:
            path: Repository path (default: current directory)
            short: Short format output (optional)
            porcelain: Machine-readable output (optional)

        Returns:
            Status information
        """
        path = params.get("path", ".")
        short = params.get("short", False)
        porcelain = params.get("porcelain", False)

        # #24: Validate path
        _validate_path(path, "path")

        args = ["status"]
        if short:
            args.append("-s")
        if porcelain:
            args.append("--porcelain")

        result = await self._run_git(args, cwd=path)

        if result["success"]:
            # Parse status output
            status = {
                "success": True,
                "raw": result["stdout"],
                "clean": not bool(result["stdout"].strip()),
            }

            if result["stdout"]:
                # Parse file status
                files = []
                for line in result["stdout"].split("\n"):
                    if line.strip():
                        # Format: XY filename
                        match = re.match(r"^(\S+)\s+(.+)$", line.strip())
                        if match:
                            files.append({
                                "status": match.group(1),
                                "file": match.group(2),
                            })
                status["files"] = files

            return status

        return result

    async def _add(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add files to staging.

        Params:
            path: Repository path (default: current directory)
            files: Files to add (default: '.')
            all: Add all files (optional)

        Returns:
            Add result
        """
        path = params.get("path", ".")
        files = params.get("files", ["."])
        add_all = params.get("all", False)

        # #24: Validate inputs
        _validate_path(path, "path")
        if not add_all:
            if isinstance(files, str):
                files = [files]
            for f in files:
                _validate_path(f, "file path")

        args = ["add"]

        if add_all:
            args.append("--all")
        else:
            if isinstance(files, str):
                files = [files]
            args.extend(files)

        result = await self._run_git(args, cwd=path)

        if result["success"]:
            logger.info(f"Added files to staging: {files}")
            return {"success": True, "files": files}

        return result

    async def _rm(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Remove files from staging.

        Params:
            path: Repository path (default: current directory)
            files: Files to remove
            cached: Remove from index only (optional)
            recursive: Remove directories recursively (optional)

        Returns:
            Remove result
        """
        path = params.get("path", ".")
        files = params.get("files", [])
        cached = params.get("cached", False)
        recursive = params.get("recursive", False)

        if not files:
            return {"success": False, "error": "Files to remove required"}

        # #24: Validate inputs
        _validate_path(path, "path")
        if isinstance(files, str):
            files = [files]
        for f in files:
            _validate_path(f, "file path")

        args = ["rm"]

        if cached:
            args.append("--cached")
        if recursive:
            args.append("-r")

        if isinstance(files, str):
            files = [files]
        args.extend(files)

        result = await self._run_git(args, cwd=path)

        if result["success"]:
            logger.info(f"Removed files: {files}")
            return {"success": True, "files": files}

        return result

    async def _commit(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Commit changes.

        Params:
            path: Repository path (default: current directory)
            message: Commit message
            author: Author name (optional)
            email: Author email (optional)
            amend: Amend previous commit (optional)
            allow_empty: Allow empty commit (optional)

        Returns:
            Commit result with hash
        """
        path = params.get("path", ".")
        message = params.get("message", "")
        author = params.get("author")
        email = params.get("email")
        amend = params.get("amend", False)
        allow_empty = params.get("allow_empty", False)

        if not message and not amend:
            return {"success": False, "error": "Commit message required"}

        # #24: Validate inputs
        _validate_path(path, "path")
        if author:
            _CONFIG_VALUE_RE.match(author) or (_ for _ in ()).throw(
                ValueError(f"Invalid author: {author!r}")
            )
        if email:
            if not re.match(r'^[^\s@\n\r]+@[^\s@\n\r]+\.[^\s@\n\r]+$', email):
                raise ValueError(f"Invalid email: {email!r}")

        args = ["commit"]

        if message:
            args.extend(["-m", message])
        if amend:
            args.append("--amend")
        if allow_empty:
            args.append("--allow-empty")

        # Build environment for author
        env = {}
        if author:
            env["GIT_AUTHOR_NAME"] = author
            env["GIT_COMMITTER_NAME"] = author
        if email:
            env["GIT_AUTHOR_EMAIL"] = email
            env["GIT_COMMITTER_EMAIL"] = email

        result = await self._run_git(args, cwd=path, env=env)

        if result["success"]:
            # Get commit hash
            hash_result = await self._run_git(
                ["rev-parse", "HEAD"],
                cwd=path
            )
            commit_hash = hash_result.get("stdout", "")[:8] if hash_result["success"] else "unknown"

            logger.info(f"Committed: {commit_hash}")
            return {
                "success": True,
                "message": message,
                "hash": commit_hash,
                "full_hash": hash_result.get("stdout", ""),
            }

        return result

    async def _push(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Push to remote.

        Params:
            path: Repository path (default: current directory)
            remote: Remote name (default: 'origin')
            branch: Branch name (optional)
            force: Force push (optional)
            tags: Push tags (optional)
            set_upstream: Set upstream (optional)

        Returns:
            Push result
        """
        path = params.get("path", ".")
        remote = params.get("remote", "origin")
        branch = params.get("branch")
        force = params.get("force", False)
        tags = params.get("tags", False)
        set_upstream = params.get("set_upstream", False)

        # #24: Validate inputs
        _validate_path(path, "path")
        _validate_ref(remote, "remote")
        if branch:
            _validate_ref(branch, "branch")

        args = ["push"]

        if force:
            args.append("--force")
        if tags:
            args.append("--tags")
        if set_upstream and branch:
            args.extend(["--set-upstream", remote, branch])
        else:
            args.append(remote)
            if branch:
                args.append(branch)

        result = await self._run_git(args, cwd=path)

        if result["success"]:
            logger.info(f"Pushed to {remote}/{branch or 'current'}")
            return {
                "success": True,
                "remote": remote,
                "branch": branch,
            }

        return result

    async def _pull(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Pull from remote.

        Params:
            path: Repository path (default: current directory)
            remote: Remote name (default: 'origin')
            branch: Branch name (optional)
            rebase: Use rebase instead of merge (optional)
            fast_forward: Use fast-forward only (optional)

        Returns:
            Pull result
        """
        path = params.get("path", ".")
        remote = params.get("remote", "origin")
        branch = params.get("branch")
        rebase = params.get("rebase", False)
        ff_only = params.get("fast_forward", False)

        # #24: Validate inputs
        _validate_path(path, "path")
        _validate_ref(remote, "remote")
        if branch:
            _validate_ref(branch, "branch")

        args = ["pull"]

        if rebase:
            args.append("--rebase")
        if ff_only:
            args.append("--ff-only")

        args.append(remote)
        if branch:
            args.append(branch)

        result = await self._run_git(args, cwd=path)

        if result["success"]:
            logger.info(f"Pulled from {remote}/{branch or 'current'}")
            return {
                "success": True,
                "remote": remote,
                "branch": branch,
                "output": result["stdout"],
            }

        return result

    async def _fetch(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fetch from remote.

        Params:
            path: Repository path (default: current directory)
            remote: Remote name (default: 'origin')
            branch: Branch name (optional)
            tags: Fetch tags (optional)
            prune: Prune deleted branches (optional)

        Returns:
            Fetch result
        """
        path = params.get("path", ".")
        remote = params.get("remote", "origin")
        branch = params.get("branch")
        tags = params.get("tags", False)
        prune = params.get("prune", False)

        # #24: Validate inputs
        _validate_path(path, "path")
        _validate_ref(remote, "remote")
        if branch:
            _validate_ref(branch, "branch")

        args = ["fetch"]

        if tags:
            args.append("--tags")
        if prune:
            args.append("--prune")

        args.append(remote)
        if branch:
            args.append(branch)

        result = await self._run_git(args, cwd=path)

        if result["success"]:
            logger.info(f"Fetched from {remote}")
            return {
                "success": True,
                "remote": remote,
                "branch": branch,
            }

        return result

    async def _branch(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Branch operations.

        Params:
            path: Repository path (default: current directory)
            name: Branch name (for create/delete)
            action: 'list', 'create', 'delete' (default: 'list')
            start_point: Starting point for new branch (optional)
            force: Force create/delete (optional)

        Returns:
            Branch result
        """
        path = params.get("path", ".")
        name = params.get("name")
        action = params.get("action", "list")
        start_point = params.get("start_point")
        force = params.get("force", False)

        # #24: Validate inputs
        _validate_path(path, "path")
        if action not in _REF_ACTIONS:
            return {"success": False, "error": f"Unknown action: {action}. Must be one of {sorted(_REF_ACTIONS)}"}
        if name:
            _validate_ref(name, "branch name")
        if start_point:
            _validate_commit_hash(start_point)

        if action == "list":
            args = ["branch", "-a"]  # List all branches
            result = await self._run_git(args, cwd=path)

            if result["success"]:
                branches = []
                current = None
                for line in result["stdout"].split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("* "):
                        current = line[2:]
                        branches.append({"name": current, "current": True})
                    else:
                        branches.append({"name": line, "current": False})

                return {
                    "success": True,
                    "branches": branches,
                    "current": current,
                }

        elif action == "create":
            if not name:
                return {"success": False, "error": "Branch name required"}

            args = ["branch"]
            if force:
                args.append("-f")
            args.append(name)
            if start_point:
                args.append(start_point)

            result = await self._run_git(args, cwd=path)

            if result["success"]:
                logger.info(f"Created branch: {name}")
                return {"success": True, "branch": name}

        elif action == "delete":
            if not name:
                return {"success": False, "error": "Branch name required"}

            args = ["branch", "-d" if not force else "-D", name]
            result = await self._run_git(args, cwd=path)

            if result["success"]:
                logger.info(f"Deleted branch: {name}")
                return {"success": True, "branch": name}

        return {"success": False, "error": f"Unknown action: {action}"}

    async def _checkout(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Checkout branch or files.

        Params:
            path: Repository path (default: current directory)
            branch: Branch to checkout
            files: Files to checkout (optional)
            create: Create new branch (optional)
            force: Force checkout (optional)

        Returns:
            Checkout result
        """
        path = params.get("path", ".")
        branch = params.get("branch")
        files = params.get("files")
        create = params.get("create", False)
        force = params.get("force", False)

        # #24: Validate inputs
        _validate_path(path, "path")
        if branch:
            _validate_ref(branch, "branch")
        if files:
            if isinstance(files, str):
                _validate_path(files, "file path")
            else:
                for f in files:
                    _validate_path(f, "file path")

        args = ["checkout"]

        if force:
            args.append("-f")

        if create and branch:
            args.extend(["-b", branch])
        elif branch:
            args.append(branch)

        if files:
            args.append("--")
            if isinstance(files, str):
                args.append(files)
            else:
                args.extend(files)

        result = await self._run_git(args, cwd=path)

        if result["success"]:
            logger.info(f"Checked out: {branch or files}")
            return {
                "success": True,
                "branch": branch,
                "files": files,
            }

        return result

    async def _merge(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge branches.

        Params:
            path: Repository path (default: current directory)
            branch: Branch to merge
            message: Merge commit message (optional)
            fast_forward: Fast-forward only (optional)
            no_ff: No fast-forward (optional)
            squash: Squash merge (optional)

        Returns:
            Merge result
        """
        path = params.get("path", ".")
        branch = params.get("branch", "")
        message = params.get("message")
        ff_only = params.get("fast_forward", False)
        no_ff = params.get("no_ff", False)
        squash = params.get("squash", False)

        if not branch:
            return {"success": False, "error": "Branch to merge required"}

        # #24: Validate inputs
        _validate_path(path, "path")
        _validate_ref(branch, "branch")

        args = ["merge"]

        if ff_only:
            args.append("--ff-only")
        if no_ff:
            args.append("--no-ff")
        if squash:
            args.append("--squash")
        if message:
            args.extend(["-m", message])

        args.append(branch)

        result = await self._run_git(args, cwd=path)

        if result["success"]:
            logger.info(f"Merged: {branch}")
            return {
                "success": True,
                "branch": branch,
                "output": result["stdout"],
            }

        return result

    async def _tag(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Tag operations.

        Params:
            path: Repository path (default: current directory)
            name: Tag name
            action: 'list', 'create', 'delete' (default: 'list')
            message: Tag message (annotated tag)
            commit: Commit to tag (optional)
            force: Force create (optional)

        Returns:
            Tag result
        """
        path = params.get("path", ".")
        name = params.get("name")
        action = params.get("action", "list")
        message = params.get("message")
        commit = params.get("commit")
        force = params.get("force", False)

        # #24: Validate inputs
        _validate_path(path, "path")
        if action not in _REF_ACTIONS:
            return {"success": False, "error": f"Unknown action: {action}. Must be one of {sorted(_REF_ACTIONS)}"}
        if name:
            _validate_ref(name, "tag name")
        if commit:
            _validate_commit_hash(commit)

        if action == "list":
            args = ["tag", "-l"]
            result = await self._run_git(args, cwd=path)

            if result["success"]:
                tags = [t for t in result["stdout"].split("\n") if t.strip()]
                return {"success": True, "tags": tags}

        elif action == "create":
            if not name:
                return {"success": False, "error": "Tag name required"}

            args = ["tag"]
            if force:
                args.append("-f")
            if message:
                args.extend(["-a", name, "-m", message])
            else:
                args.append(name)
            if commit:
                args.append(commit)

            result = await self._run_git(args, cwd=path)

            if result["success"]:
                logger.info(f"Created tag: {name}")
                return {"success": True, "tag": name}

        elif action == "delete":
            if not name:
                return {"success": False, "error": "Tag name required"}

            args = ["tag", "-d", name]
            result = await self._run_git(args, cwd=path)

            if result["success"]:
                logger.info(f"Deleted tag: {name}")
                return {"success": True, "tag": name}

        return {"success": False, "error": f"Unknown action: {action}"}

    async def _log(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Show commit log.

        Params:
            path: Repository path (default: current directory)
            count: Number of commits (default: 10)
            branch: Branch or revision (optional)
            oneline: One-line format (optional)
            format: Custom format (optional)

        Returns:
            Commit log
        """
        path = params.get("path", ".")
        count = params.get("count", 10)
        branch = params.get("branch")
        oneline = params.get("oneline", False)
        format_str = params.get("format")

        # #24: Validate inputs
        _validate_path(path, "path")
        try:
            count = int(count)
            if count < 1:
                raise ValueError
        except (ValueError, TypeError):
            return {"success": False, "error": f"Invalid count: {count!r}"}
        if branch:
            _validate_ref(branch, "branch")
        if format_str and not _SAFE_FORMAT_RE.match(format_str):
            return {"success": False, "error": f"Invalid format string: {format_str!r}"}

        args = ["log"]

        if oneline:
            args.append("--oneline")
        elif format_str:
            args.extend(["--format", format_str])
        else:
            # Default format with hash, author, date, message
            args.extend(["--format", "%H|%an|%ae|%ad|%s"])

        args.extend([f"-{count}"])

        if branch:
            args.append(branch)

        result = await self._run_git(args, cwd=path)

        if result["success"]:
            commits = []
            for line in result["stdout"].split("\n"):
                if not line.strip():
                    continue
                if oneline:
                    parts = line.split(None, 1)
                    commits.append({
                        "hash": parts[0] if parts else "",
                        "message": parts[1] if len(parts) > 1 else "",
                    })
                elif "|" in line:
                    parts = line.split("|")
                    commits.append({
                        "hash": parts[0] if len(parts) > 0 else "",
                        "author": parts[1] if len(parts) > 1 else "",
                        "email": parts[2] if len(parts) > 2 else "",
                        "date": parts[3] if len(parts) > 3 else "",
                        "message": parts[4] if len(parts) > 4 else "",
                    })

            return {
                "success": True,
                "commits": commits,
                "count": len(commits),
            }

        return result

    async def _diff(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Show differences.

        Params:
            path: Repository path (default: current directory)
            commit1: First commit (optional)
            commit2: Second commit (optional)
            staged: Show staged changes (optional)
            files: Files to diff (optional)

        Returns:
            Diff output
        """
        path = params.get("path", ".")
        commit1 = params.get("commit1")
        commit2 = params.get("commit2")
        staged = params.get("staged", False)
        files = params.get("files")

        # #24: Validate inputs
        _validate_path(path, "path")
        if commit1:
            _validate_commit_hash(commit1)
        if commit2:
            _validate_commit_hash(commit2)
        if files:
            if isinstance(files, str):
                _validate_path(files, "file path")
            else:
                for f in files:
                    _validate_path(f, "file path")

        args = ["diff"]

        if staged:
            args.append("--staged")

        if commit1 and commit2:
            # #24: Use two separate args instead of ".." range syntax
            # to avoid string interpolation injection
            args.extend([commit1, commit2])
        elif commit1:
            args.append(commit1)

        if files:
            args.append("--")
            if isinstance(files, str):
                args.append(files)
            else:
                args.extend(files)

        result = await self._run_git(args, cwd=path)

        if result["success"]:
            return {
                "success": True,
                "diff": result["stdout"],
                "has_changes": bool(result["stdout"].strip()),
            }

        return result

    async def _remote(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Remote operations.

        Params:
            path: Repository path (default: current directory)
            action: 'list', 'add', 'remove', 'get_url' (default: 'list')
            name: Remote name
            url: Remote URL (for add)

        Returns:
            Remote info
        """
        path = params.get("path", ".")
        action = params.get("action", "list")
        name = params.get("name")
        url = params.get("url")

        # #24: Validate inputs
        _validate_path(path, "path")
        if action not in _REMOTE_ACTIONS:
            return {"success": False, "error": f"Unknown action: {action}. Must be one of {sorted(_REMOTE_ACTIONS)}"}
        if name:
            _validate_ref(name, "remote name")

        if action == "list":
            args = ["remote", "-v"]
            result = await self._run_git(args, cwd=path)

            if result["success"]:
                remotes = {}
                for line in result["stdout"].split("\n"):
                    if not line.strip():
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        remote_name = parts[0]
                        remote_url = parts[1]
                        if remote_name not in remotes:
                            remotes[remote_name] = {"name": remote_name, "url": remote_url}

                return {"success": True, "remotes": remotes}

        elif action == "add":
            if not name or not url:
                return {"success": False, "error": "Remote name and URL required"}

            args = ["remote", "add", name, url]
            result = await self._run_git(args, cwd=path)

            if result["success"]:
                logger.info(f"Added remote: {name} -> {url}")
                return {"success": True, "name": name, "url": url}

        elif action == "remove":
            if not name:
                return {"success": False, "error": "Remote name required"}

            args = ["remote", "remove", name]
            result = await self._run_git(args, cwd=path)

            if result["success"]:
                logger.info(f"Removed remote: {name}")
                return {"success": True, "name": name}

        elif action == "get_url":
            if not name:
                return {"success": False, "error": "Remote name required"}

            args = ["remote", "get-url", name]
            result = await self._run_git(args, cwd=path)

            if result["success"]:
                return {"success": True, "name": name, "url": result["stdout"]}

        return {"success": False, "error": f"Unknown action: {action}"}

    async def _reset(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Reset changes.

        Params:
            path: Repository path (default: current directory)
            mode: 'soft', 'mixed', 'hard', 'merge' (default: 'mixed')
            commit: Commit to reset to (optional)

        Returns:
            Reset result
        """
        path = params.get("path", ".")
        mode = params.get("mode", "mixed")
        commit = params.get("commit")

        # #24: Validate inputs
        _validate_path(path, "path")
        if mode not in _RESET_MODES:
            return {"success": False, "error": f"Invalid reset mode: {mode!r}. Must be one of {sorted(_RESET_MODES)}"}
        if commit:
            _validate_commit_hash(commit)

        args = ["reset"]

        if mode in ["soft", "mixed", "hard", "merge"]:
            args.append(f"--{mode}")

        if commit:
            args.append(commit)

        result = await self._run_git(args, cwd=path)

        if result["success"]:
            logger.info(f"Reset: {mode}")
            return {"success": True, "mode": mode, "commit": commit}

        return result

    async def _stash(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Stash operations.

        Params:
            path: Repository path (default: current directory)
            action: 'push', 'pop', 'list', 'drop', 'apply' (default: 'push')
            message: Stash message (for push)
            stash: Stash reference (for pop/apply/drop, e.g., 'stash@{0}')

        Returns:
            Stash result
        """
        path = params.get("path", ".")
        action = params.get("action", "push")
        message = params.get("message")
        stash = params.get("stash", "stash@{0}")

        # #24: Validate inputs
        _validate_path(path, "path")
        if action not in _STASH_ACTIONS:
            return {"success": False, "error": f"Unknown action: {action}. Must be one of {sorted(_STASH_ACTIONS)}"}
        # Validate stash reference format (e.g., stash@{0})
        if action in ("pop", "apply", "drop"):
            if not re.match(r'^stash@\{\d+\}$', stash):
                return {"success": False, "error": f"Invalid stash reference: {stash!r}"}

        if action == "push":
            args = ["stash", "push"]
            if message:
                args.extend(["-m", message])
            result = await self._run_git(args, cwd=path)

            if result["success"]:
                logger.info("Stashed changes")
                return {"success": True, "message": message}

        elif action == "pop":
            args = ["stash", "pop", stash]
            result = await self._run_git(args, cwd=path)

            if result["success"]:
                logger.info(f"Popped stash: {stash}")
                return {"success": True, "stash": stash}

        elif action == "apply":
            args = ["stash", "apply", stash]
            result = await self._run_git(args, cwd=path)

            if result["success"]:
                logger.info(f"Applied stash: {stash}")
                return {"success": True, "stash": stash}

        elif action == "drop":
            args = ["stash", "drop", stash]
            result = await self._run_git(args, cwd=path)

            if result["success"]:
                logger.info(f"Dropped stash: {stash}")
                return {"success": True, "stash": stash}

        elif action == "list":
            args = ["stash", "list"]
            result = await self._run_git(args, cwd=path)

            if result["success"]:
                stashes = []
                for line in result["stdout"].split("\n"):
                    if line.strip():
                        stashes.append(line.strip())
                return {"success": True, "stashes": stashes}

        return {"success": False, "error": f"Unknown action: {action}"}

    async def _config(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Git configuration.

        Params:
            path: Repository path (default: current directory)
            key: Config key
            value: Config value (optional, for get if not provided)
            global_: Global config (optional)
            action: 'get', 'set', 'list' (default: 'get')

        Returns:
            Config result
        """
        path = params.get("path", ".")
        key = params.get("key", "")
        value = params.get("value")
        global_ = params.get("global_", False)
        action = params.get("action", "get")

        # #24: Validate inputs
        _validate_path(path, "path")
        if action not in _CONFIG_ACTIONS:
            return {"success": False, "error": f"Unknown action: {action}. Must be one of {sorted(_CONFIG_ACTIONS)}"}
        if key:
            if not _CONFIG_KEY_RE.match(key):
                return {"success": False, "error": f"Invalid config key: {key!r}"}
        if value is not None and not _CONFIG_VALUE_RE.match(str(value)):
            return {"success": False, "error": f"Invalid config value: {value!r}"}

        args = ["config"]

        if global_:
            args.append("--global")

        if action == "list":
            args.append("-l")
            result = await self._run_git(args, cwd=path)

            if result["success"]:
                config = {}
                for line in result["stdout"].split("\n"):
                    if "=" in line:
                        k, v = line.split("=", 1)
                        config[k] = v
                return {"success": True, "config": config}

        elif action == "get":
            if not key:
                return {"success": False, "error": "Config key required"}

            args.append("--get")
            args.append(key)
            result = await self._run_git(args, cwd=path)

            if result["success"]:
                return {"success": True, "key": key, "value": result["stdout"]}

            return {"success": True, "key": key, "value": None}

        elif action == "set":
            if not key or value is None:
                return {"success": False, "error": "Config key and value required"}

            args.extend([key, value])
            result = await self._run_git(args, cwd=path)

            if result["success"]:
                logger.info(f"Set config: {key} = {value}")
                return {"success": True, "key": key, "value": value}

        return {"success": False, "error": f"Unknown action: {action}"}
