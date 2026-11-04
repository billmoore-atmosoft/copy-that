# Contributing to CopyThat

CopyThat is a hobby project, shared as is. Pull requests may not get reviewed, issues may not get answered, and there's no schedule for fixes or new features. You're welcome to fork it and make it your own.

If you still want to send a change, the notes below will help. This project targets **Windows 10/11** with local OpenVINO inference.

## Development setup

1. Install **Python 3.10** (the version used for the lock file).
2. From the repository root:

```powershell
.\Start-Dictation.ps1 -Setup
```

Setup installs dependencies from **`requirements.lock.txt`**. Use the lock file for reproducible environments; `requirements.txt` lists compatible ranges.

3. Run the app from a checkout:

```powershell
.\Start-Dictation.ps1
```

Use `-DataDir` or `COPYTHAT_DATA_DIR` to keep models and config outside synced folders (see README).

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp=.test-temp
```

Optional smoke scripts (see README) exercise clipboard, UI, and model loading. Do not run paste smoke while typing elsewhere.

## Pull requests

- Keep changes focused; match existing style and naming.
- Add or update tests for behavior changes.
- Run `pytest` before submitting.
- Update README or SECURITY.md when user-visible behavior or trust boundaries change.

## Building the Windows installer

See README **Build the installer**. Requires NSIS and `requirements-build.txt`.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Be respectful in issues and reviews.

## Security

See [SECURITY.md](SECURITY.md) for the local threat model and how to report a problem.
