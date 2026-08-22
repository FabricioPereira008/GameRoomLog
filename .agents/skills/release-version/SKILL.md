---
name: release-version
description: >-
  Executes the release process for new versions of GameRoomLog. Use this skill whenever
  the user asks to release a new version (e.g. "lance a versão 0.2.3", "crie uma nova versão",
  "bump version", "gerar release"). It runs all tests, updates version strings in all
  files, updates CHANGELOG.md, and creates the git commit and tag.
---

# Release Version Workflow (GameRoomLog)

This skill automates the end-to-end release process for new versions of the GameRoomLog application.

## Workflow Overview

When releasing a new version, the agent must execute the following sequence:

1. **Pre-flight Check**: Run the complete automated test suite (`pytest`) to ensure no existing regressions.
2. **Version Propagation**: Update the version number across all layers:
   - `backend/app/core/config.py` (`VERSION`)
   - `backend/tests/test_api.py` (`assert response.json()["version"] == ...`)
   - `frontend_desktop/tests/test_api_client.py` (`"version": ...`)
   - `frontend_desktop/views/components/settings_view.py` (`GameRoomLog v...`)
   - `frontend_desktop/views/components/sidebar.py` (`v... • Linux Native`)
   - `frontend_desktop/views/main_window.py` (`GameRoomLog v... Online`)
3. **Changelog Generation**: Add a structured release entry in `CHANGELOG.md` adhering to the *Keep a Changelog* format.
4. **Post-update Test Run**: Re-run the test suite to ensure the updated version assertions pass.
5. **Git Commit & Tag**: Create a signed/annotated git commit `chore(release): bump version to v<VERSION>` and a tag `v<VERSION>`.

---

## Execution Options

### Option A: Using the Automated Release Helper (Recommended)

Run the release script directly from the project root:

```bash
./venv/bin/python .agents/skills/release-version/scripts/release.py <NEW_VERSION> ["Release notes in Markdown"]
```

**Example:**
```bash
./venv/bin/python .agents/skills/release-version/scripts/release.py 0.2.3 "### Adicionado\n- Nova tela de estatísticas.\n\n### Corrigido\n- Bug no scroll da lista."
```

---

### Option B: Manual Execution Steps

If running manually step-by-step:

1. **Run tests:**
   ```bash
   ./venv/bin/pytest -v
   ```
2. **Update version strings in all 6 files listed above.**
3. **Update `CHANGELOG.md`:**
   Insert `## [<NEW_VERSION>] - YYYY-MM-DD` at the top of the version list.
4. **Run tests again:**
   ```bash
   ./venv/bin/pytest -v
   ```
5. **Create Git commit and tag:**
   ```bash
   git add .
   git commit -m "chore(release): bump version to v<NEW_VERSION>"
   git tag -a v<NEW_VERSION> -m "Release v<NEW_VERSION>"
   ```
