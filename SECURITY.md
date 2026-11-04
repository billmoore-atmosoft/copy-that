# Security Policy

## Supported versions

Only the latest release is considered. CopyThat is a hobby project, so there's no promise of a fix or a date for one.

## Reporting a problem

Open a regular GitHub issue and leave out anything sensitive, such as personal data or your dictated text. Replies are best effort.

## Threat model (what CopyThat is designed for)

CopyThat is a **local-first** desktop dictation utility for a single Windows user session:

- Speech and optional “Polish” cleanup run **on your machine** using OpenVINO models you download from Hugging Face.
- Dictated text is pasted into the **currently focused** application via the clipboard and simulated Ctrl+V.
- Optional take logging writes **WAV audio and transcripts** to a folder you configure.

CopyThat is **not** a multi-tenant service, sandbox, or secret store.

## Trust boundaries

| Asset | Risk | Mitigation |
| --- | --- | --- |
| **Clipboard** | Previous clipboard text may be overwritten during paste; non-text clipboard content is not preserved. | Documented in README; paste uses restore checks. |
| **Polish (Qwen) models** | Loading arbitrary OpenVINO graphs executes native code in-process. | The app loads Polish only from `%LOCALAPPDATA%\CopyThat\models` (or your `COPYTHAT_DATA_DIR/models`), with a complete `model-manifest.json`; otherwise it uses rules only. The manifest checks file sizes, so this guards against mistakes, not against someone who can already change your files. |
| **Speech models** | Same as polish; models are selected from the built-in registry or Settings downloads. | Pinned Hugging Face revisions; manifest size checks after download. |
| **Take logs** | Contain raw audio and transcripts. | Blocked under the git repo and common cloud-sync paths; off by default. |
| **config.json** | Can enable take logging, dictionary, and polish paths. | Values are validated on load and save. Settings also checks paths and dictionary size. |
| **Prompt injection (Polish)** | Transcript text is sent to the local cleanup model. | Drift guards, deadline fallback, and rules-only fallback; see `cleanup.py`. |

## Releases and binaries

Installer builds are **unsigned** today. Verify downloads from official GitHub releases only. Prefer building from source if you need reproducible artifacts.

## Out of scope

- Pasting into applications running as **Administrator** (blocked by design).
- Protecting against malware already running on the same user account.
- Network exfiltration: dictation does not upload audio or text; model downloads are explicit user actions.
