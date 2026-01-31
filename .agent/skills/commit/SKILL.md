---
name: commit
description: Generate conventional commit messages and commit changes
---

# Commit

## When to use this skill

- Use this when I ask you to commit changes.
- Use this when you need to generate a standardized, descriptive commit message.

## How to use it

1. **Review Changes**:
   - Run `git status` to identify changed files.
   - Run `git diff` or `git diff --cached` to inspect specific changes.

2. **Stage Changes**:
   - Run `git add <file>` for the files you intend to commit.

3. **Construct Commit Message**:
   - Follow the **Conventional Commits** specification:

     ```text
     <type>(<scope>): <description>

     [optional body]

     [optional footer]
     ```

   - **Type**: Must be one of:
     - `feat`: New feature
     - `fix`: Bug fix
     - `docs`: Documentation changes
     - `style`: Formatting, missing semi-colons, etc.
     - `refactor`: Code change that neither fixes a bug nor adds a feature
     - `perf`: Code change that improves performance
     - `test`: Adding or correcting tests
     - `build`: Changes that affect the build system or external dependencies
     - `ci`: Changes to CI configuration files and scripts
     - `chore`: Other changes that don't modify src or test files
     - `revert`: Reverts a previous commit
   - **Scope**: Optional but recommended (e.g., `parser`, `ui`).
   - **Description**: Short, imperative summary (e.g., "add ability to parse arrays").

4. **Validation Guidelines**:
   - Use the imperative mood in the description (e.g., "add" not "added").
   - Breaking changes should be noted in the footer (e.g., `BREAKING CHANGE: ...`) or with a `!` after the type/scope (e.g., `feat!: ...`).
   - See [Conventional Commits](https://www.conventionalcommits.org/) for full details.

5. **Execute Commit**:
   - Run `git commit -m "type(scope): description"`.
   - Include body or footer if necessary using the header/body format.
