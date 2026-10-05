# Changelog — 2026-10-05

## CI dependency path correction

- Corrected the platform validation workflow to install from the tracked root `requirements.txt`.
- Added Ticket 07 regression coverage for dependency files resolved against effective workflow working directories.

## CI YAML test dependency

- Declared pinned `PyYAML==6.0.3` in root `requirements.txt` for platform-test collection.
- Added Ticket 08 regression coverage and verified clean dependency installation supports platform-test collection.

Author Name: Aguda, Maurice
