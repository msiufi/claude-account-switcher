# Contributing

Bug reports, compatibility reports, translations, documentation fixes and pull requests are welcome. For a larger change to how profiles are stored or moved, open an issue first so we can agree on the approach.

## Project layout

- `windows/`: Electron tray app. `core.js` holds the switching logic (no Electron dependency), `main.js` the tray and window, `manage.html` the UI.
- `python/`: single-file Python + Tkinter version for Windows, macOS and Linux.

Both versions must stay compatible with the same profile folder (`Claude-Switcher/profiles` and `state.json`), so users can move between them.

## Windows app

```bash
cd windows
npm ci
npm test        # switching logic, runs on any OS
npm start       # run the app (on Windows)
npm run dist    # build installer + portable into windows/dist (on Windows)
```

## Python version

```bash
cd python
python -m py_compile claude_switcher.py
python -m unittest discover tests -v
python claude_switcher.py
```

## Testing changes to profile handling

The automated tests use a temporary folder and never touch a real Claude installation. When you test by hand, use disposable profiles, a test OS account, or a backup of your Claude data. Check that each profile keeps its own session after a round trip, and check what happens when a step fails.

Keep logs and screenshots free of account emails, session files and private paths.

## Pull requests

Describe what changed, how you tested it, and which OS and Claude Desktop version (and installation channel: direct download or Microsoft Store) you used. CI runs the tests on Windows, macOS and Linux.

## Releases (maintainers)

1. Bump `version` in `windows/package.json`.
2. Commit, then tag and push: `git tag v1.1.0 && git push origin v1.1.0`.
3. The Release workflow builds the installer, portable app and Python zip, and publishes them with checksums.
