# Contributing to IPSUM

Thank you for investing your time in contributing to our project! 

To ensure a smooth collaboration process and maintain code quality, please review the following guidelines before getting started.

## 1. Official Language
**English is the official language of this project.**
To maintain consistency for international contributors:
- **Code:** Variable names, function definitions, classes, and file names must be in English.
- **Documentation:** Docstrings, inline comments, commit messages, and Pull Requests must be written in English.
- **Logs:** All application logs (`logger.info`, `logger.error`) must be in English.

## 2. Branching Strategy (Gitflow)
We follow a simplified Gitflow workflow. Please do not push directly to `main`.

- **`main`**: The stable, production-ready branch.
- **`develop`**: The main integration branch. All features are merged here first.
- **`feature/<name>`**: For new capabilities (e.g., `feature/spatial-indexing`).
- **`fix/<name>`**: For bug fixes (e.g., `fix/csv-parsing-error`).
- **`refactor/<name>`**: For code cleanup without logic changes.
- **`docs/<name>`**: For documentation updates.

### Workflow Example:
1. Checkout `develop`: `git checkout develop`
2. Create your branch: `git checkout -b feature/my-new-feature`
3. Commit your changes.
4. Open a Pull Request (PR) targeting `develop`.

## 3. Commit Messages
We adhere to the [Conventional Commits](https://www.conventionalcommits.org/) specification. This allows us to automatically generate changelogs.

**Format:** `<type>(<scope>): <short summary>`

**Allowed Types:**
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools and libraries

**Examples:**
- `feat(api): add endpoint for geodesic distance calculation`
- `fix(docker): resolve miniconda dependency conflict`
- `docs(readme): update installation steps`

## 4. Code Style
- Follow **PEP 8** guidelines for Python code.
- Ensure your code is formatted (we recommend `black` or `flake8`).
- Remove unused imports and commented-out code before committing.

## 5. Pull Requests
- Provide a clear description of what the PR does.
- Reference any related issues (e.g., "Closes #123").
- Ensure all CI checks pass (if applicable).