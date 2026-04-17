# Git Plugin

Git plugin for Cray, providing comprehensive Git repository operations.

## Features

- **Repository Management**: Clone, init, status
- **Commit Operations**: Add, commit, push, pull, fetch
- **Branch Management**: Create, list, delete, checkout, merge
- **Tag Management**: Create, list, delete tags
- **History & Diff**: View log, diff changes
- **Remote Management**: Add, remove, list remotes
- **Advanced**: Stash, reset, config

## Actions

### clone

Clone a repository.

```yaml
- name: clone-repo
  plugin: git
  action: clone
  params:
    url: https://github.com/user/repo.git
    path: ./my-repo
    branch: main
    depth: 1
```

Params:
- `url` (required): Repository URL
- `path`: Destination path
- `branch`: Branch to clone
- `depth`: Shallow clone depth
- `recursive`: Clone submodules (default: false)
- `single_branch`: Clone single branch

### init

Initialize a new repository.

```yaml
- name: init-repo
  plugin: git
  action: init
  params:
    path: ./new-repo
    bare: false
```

### status

Get repository status.

```yaml
- name: check-status
  plugin: git
  action: status
  params:
    path: ./my-repo
    short: true
```

Returns:
```json
{
  "success": true,
  "clean": false,
  "files": [
    {"status": "M", "file": "README.md"},
    {"status": "??", "file": "new_file.txt"}
  ]
}
```

### add

Add files to staging.

```yaml
- name: stage-files
  plugin: git
  action: add
  params:
    path: ./my-repo
    files: ["src/", "README.md"]
```

Or add all files:

```yaml
- name: stage-all
  plugin: git
  action: add
  params:
    path: ./my-repo
    all: true
```

### commit

Commit changes.

```yaml
- name: commit-changes
  plugin: git
  action: commit
  params:
    path: ./my-repo
    message: "Add new feature"
    author: "John Doe"
    email: "john@example.com"
```

Returns:
```json
{
  "success": true,
  "hash": "abc12345",
  "message": "Add new feature"
}
```

### push

Push to remote.

```yaml
- name: push-changes
  plugin: git
  action: push
  params:
    path: ./my-repo
    remote: origin
    branch: main
    force: false
    tags: true
```

### pull

Pull from remote.

```yaml
- name: pull-latest
  plugin: git
  action: pull
  params:
    path: ./my-repo
    remote: origin
    branch: main
    rebase: false
```

### fetch

Fetch from remote.

```yaml
- name: fetch-updates
  plugin: git
  action: fetch
  params:
    path: ./my-repo
    remote: origin
    prune: true
```

### branch

Branch operations.

**List branches:**
```yaml
- name: list-branches
  plugin: git
  action: branch
  params:
    path: ./my-repo
    action: list
```

**Create branch:**
```yaml
- name: create-branch
  plugin: git
  action: branch
  params:
    path: ./my-repo
    action: create
    name: feature/new-feature
    start_point: main
```

**Delete branch:**
```yaml
- name: delete-branch
  plugin: git
  action: branch
  params:
    path: ./my-repo
    action: delete
    name: old-branch
    force: false
```

### checkout

Checkout branch or files.

```yaml
- name: checkout-branch
  plugin: git
  action: checkout
  params:
    path: ./my-repo
    branch: develop
```

Create and checkout new branch:
```yaml
- name: checkout-new
  plugin: git
  action: checkout
  params:
    path: ./my-repo
    branch: feature/new
    create: true
```

Checkout specific files:
```yaml
- name: checkout-files
  plugin: git
  action: checkout
  params:
    path: ./my-repo
    files: ["config.yaml", "README.md"]
```

### merge

Merge branches.

```yaml
- name: merge-branch
  plugin: git
  action: merge
  params:
    path: ./my-repo
    branch: feature/new-feature
    message: "Merge feature branch"
    no_ff: true
```

### tag

Tag operations.

**List tags:**
```yaml
- name: list-tags
  plugin: git
  action: tag
  params:
    path: ./my-repo
    action: list
```

**Create tag:**
```yaml
- name: create-tag
  plugin: git
  action: tag
  params:
    path: ./my-repo
    action: create
    name: v1.0.0
    message: "Release 1.0.0"
```

**Delete tag:**
```yaml
- name: delete-tag
  plugin: git
  action: tag
  params:
    path: ./my-repo
    action: delete
    name: old-tag
```

### log

View commit history.

```yaml
- name: view-log
  plugin: git
  action: log
  params:
    path: ./my-repo
    count: 10
    branch: main
    oneline: true
```

Returns:
```json
{
  "success": true,
  "commits": [
    {"hash": "abc1234", "message": "Add feature"},
    {"hash": "def5678", "message": "Fix bug"}
  ],
  "count": 2
}
```

### diff

Show differences.

```yaml
- name: show-diff
  plugin: git
  action: diff
  params:
    path: ./my-repo
    staged: true
```

Compare commits:
```yaml
- name: compare-commits
  plugin: git
  action: diff
  params:
    path: ./my-repo
    commit1: v1.0.0
    commit2: v1.1.0
```

### remote

Remote operations.

**List remotes:**
```yaml
- name: list-remotes
  plugin: git
  action: remote
  params:
    path: ./my-repo
    action: list
```

**Add remote:**
```yaml
- name: add-remote
  plugin: git
  action: remote
  params:
    path: ./my-repo
    action: add
    name: upstream
    url: https://github.com/original/repo.git
```

**Remove remote:**
```yaml
- name: remove-remote
  plugin: git
  action: remote
  params:
    path: ./my-repo
    action: remove
    name: old-remote
```

### reset

Reset changes.

```yaml
- name: reset-hard
  plugin: git
  action: reset
  params:
    path: ./my-repo
    mode: hard
    commit: HEAD~1
```

Modes: `soft`, `mixed`, `hard`, `merge`

### stash

Stash operations.

**Stash changes:**
```yaml
- name: stash-changes
  plugin: git
  action: stash
  params:
    path: ./my-repo
    action: push
    message: "WIP: feature"
```

**List stashes:**
```yaml
- name: list-stashes
  plugin: git
  action: stash
  params:
    path: ./my-repo
    action: list
```

**Apply stash:**
```yaml
- name: apply-stash
  plugin: git
  action: stash
  params:
    path: ./my-repo
    action: apply
    stash: "stash@{0}"
```

**Pop stash:**
```yaml
- name: pop-stash
  plugin: git
  action: stash
  params:
    path: ./my-repo
    action: pop
    stash: "stash@{0}"
```

### config

Git configuration.

**Get config:**
```yaml
- name: get-config
  plugin: git
  action: config
  params:
    path: ./my-repo
    action: get
    key: user.name
```

**Set config:**
```yaml
- name: set-config
  plugin: git
  action: config
  params:
    path: ./my-repo
    action: set
    key: user.email
    value: user@example.com
    global_: true
```

**List all config:**
```yaml
- name: list-config
  plugin: git
  action: config
  params:
    path: ./my-repo
    action: list
```

## Complete Example

### Automated Release Workflow

```yaml
name: release
description: Create a release with version bump and tag

steps:
  # Check working directory is clean
  - name: check-clean
    plugin: git
    action: status
    params:
      path: ./my-project
      short: true

  # Bump version
  - name: bump-version
    plugin: shell
    action: exec
    params:
      command: |
        cd my-project
        echo "{{ input.version }}" > VERSION
      condition: "{{ steps.check-clean.clean }}"

  # Stage changes
  - name: stage
    plugin: git
    action: add
    params:
      path: ./my-project
      files: ["VERSION"]

  # Commit
  - name: commit
    plugin: git
    action: commit
    params:
      path: ./my-project
      message: "Bump version to {{ input.version }}"

  # Create tag
  - name: tag
    plugin: git
    action: tag
    params:
      path: ./my-project
      action: create
      name: "v{{ input.version }}"
      message: "Release {{ input.version }}"

  # Push
  - name: push
    plugin: git
    action: push
    params:
      path: ./my-project
      branch: main
      tags: true
```

### Sync Fork Workflow

```yaml
name: sync-fork
description: Sync fork with upstream

steps:
  - name: fetch-upstream
    plugin: git
    action: fetch
    params:
      path: ./my-fork
      remote: upstream

  - name: checkout-main
    plugin: git
    action: checkout
    params:
      path: ./my-fork
      branch: main

  - name: merge-upstream
    plugin: git
    action: merge
    params:
      path: ./my-fork
      branch: upstream/main

  - name: push-origin
    plugin: git
    action: push
    params:
      path: ./my-fork
      remote: origin
      branch: main
```

### CI/CD Git Operations

```yaml
name: ci-git
description: CI/CD git operations

steps:
  # Clone repository
  - name: clone
    plugin: git
    action: clone
    params:
      url: https://github.com/company/project.git
      path: ./build
      branch: "{{ input.branch }}"
      depth: 1

  # Get current commit info
  - name: get-commit
    plugin: git
    action: log
    params:
      path: ./build
      count: 1
      format: "%H|%s"

  # Build and test
  - name: build
    plugin: shell
    action: exec
    params:
      command: |
        cd build
        make build

  # Tag successful build
  - name: tag-build
    plugin: git
    action: tag
    params:
      path: ./build
      action: create
      name: "build-{{ input.build_number }}"
      message: "Build #{{ input.build_number }}"
    condition: "{{ steps.build.success }}"
```

## Error Handling

All actions return consistent format:

```json
{
  "success": true,
  // ... action-specific data
}
```

On error:
```json
{
  "success": false,
  "error": "fatal: not a git repository"
}
```

## Notes

- All `path` parameters default to current directory (`.`)
- Git commands run asynchronously without blocking
- Environment variables (like `GIT_AUTHOR_NAME`) are supported
- Works with SSH keys and credential helpers configured in your environment
