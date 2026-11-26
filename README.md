# Claude Account Switcher

Switch between Claude Desktop accounts on the same computer with separate local profiles. Sign in through Claude Desktop once per profile, then select a saved account to reopen Claude with that profile. If a session expires, sign in again in Claude Desktop.

This is an independent utility for Windows and macOS. The interface is currently in Spanish. See the [Spanish guide](LEEME.md).

## Run from source

1. Install Claude Desktop and Python 3.8 or later with Tkinter. Run `python -m tkinter` on Windows or `python3 -m tkinter` on macOS to check your Python installation.
2. Clone this repository or use **Code → Download ZIP**, then extract it.
3. From the project folder, run `python claude_switcher.py` on Windows or `python3 claude_switcher.py` on macOS.

In the switcher, click **Guardar cuenta actual** to name the account already open in Claude. Click **Añadir cuenta** to open a fresh profile and sign in through Claude Desktop. Click a profile to switch. Right-click a profile to rename or delete it. With the switcher window focused, use Ctrl+1 through Ctrl+9 on Windows or Cmd+1 through Cmd+9 on macOS.

The CLI also supports `list`, `save NAME`, `new NAME`, `switch NAME`, `rename OLD NEW`, and `delete NAME`. Pass the command after `claude_switcher.py`.

## How profiles work

The switcher closes Claude Desktop, moves its local data directory into the active profile, moves the selected profile into place, and relaunches Claude. The switcher carries forward the current `claude_desktop_config.json` when present. Keep profiles on the same computer and OS account.

| Platform | Switcher data |
| --- | --- |
| Windows | `%APPDATA%\Claude-Switcher` |
| macOS | `~/Library/Application Support/Claude-Switcher` |

The `profiles/` directory can contain active session material. Keep it private and exclude it from issue attachments and repositories. Back up your Claude Desktop data before trying the switcher, and finish active work before switching because Claude Desktop will close. Compatibility can vary with Claude Desktop packaging and updates.

## Feedback and contributions

Report bugs or suggest features through [GitHub Issues](https://github.com/msiufi/claude-account-switcher/issues). See [Contributing](CONTRIBUTING.md) for setup, testing, and pull requests. Use the [security policy](SECURITY.md) for sensitive reports.

Claude is a product of Anthropic. This project is independently maintained.
