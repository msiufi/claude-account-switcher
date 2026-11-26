# Contributing

Bug reports, compatibility reports, documentation fixes, and pull requests are welcome. For a larger change to how profiles are stored or moved, open an issue first so maintainers can discuss the approach with you.

## Development

1. Fork and clone the repository.
2. Run `python claude_switcher.py` on Windows or `python3 claude_switcher.py` on macOS.
3. Run `python -m py_compile claude_switcher.py` to check syntax.
4. Open a pull request describing what changed, how you tested it, and which operating system and Claude Desktop version you used.

For changes to profile management, test with disposable profiles and a temporary data directory, or with a test OS account. Verify that each profile retains its own data after a round trip and check failure behavior before using real account data. Keep logs and screenshots free of account identifiers, session material, and private file paths.
