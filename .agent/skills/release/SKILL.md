---
name: release
description: Create a new release for the current repository in GitHub
---

# Release

## When to use this skill

- Use this when I ask you to release a new version of the repository.

## How to use it

1. **Sync with Remote**:
   - Run `git checkout main && git pull` to ensure you are on the latest commit.
   - Run `git fetch --tags` to ensure you have all remote tags.

2. **Identify Latest Release**:
   - Use the `get_latest_release` tool from `github-mcp-server` to find the latest version tag (e.g., `v1.2.3`).
   - If that fails or returns no release, check locally with `git describe --tags --abbrev=0`.

3. **Analyze Changes**:
   - Run `git log <latest_tag>..HEAD --oneline` to see commits since the last release.
   - If there are no commits, inform the user that there are no changes to release.

4. **Prepare Release Notes**:
   - Create a description following this format:

     ```markdown
     ## [X.Y.Z](https://github.com/owner/repo/compare/vPrevious...vNew) (YYYY-MM-DD)

     ### Added
     - Feature A

     ### Changed
     - Change B

     ### Fixed
     - Fix C
     ```

5. **Calculate New Version (Semantic Versioning)**:
   - Identify the type of changes made:
     - **MAJOR**: Breaking changes (e.g., incompatible API, significant restructuring).
     - **MINOR**: New features (backward compatible).
     - **PATCH**: Bug fixes or minor improvements (backward compatible).
   - Follow the [SemVer rules](https://aws.amazon.com/blogs/devops/using-semantic-versioning-to-simplify-release-management/) for incrementing:
     - Increment **Major** (X.0.0) for breaking changes. Reset Minor and Patch to 0.
     - Increment **Minor** (X.Y.0) for features. Reset Patch to 0.
     - Increment **Patch** (X.Y.Z) for fixes.

6. **Create Tag**:
   - Run `git tag -a vX.Y.Z -m "Release vX.Y.Z"`.
   - Run `git push origin vX.Y.Z`.

7. **Create GitHub Release**:
   - Run `gh release create vX.Y.Z --title "vX.Y.Z" --notes "<body>"` where `<body>` is the release notes prepared in step 4.
