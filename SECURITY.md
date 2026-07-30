# Security policy

## Supported version

Security fixes are provided for the latest tagged release.

## Reporting

Please use GitHub's private vulnerability reporting for path traversal,
archive extraction, installer rollback, or dependency issues. Do not open a
public issue containing a working exploit or private data.

Include:

- affected version and operating system;
- the smallest safe reproduction;
- expected and actual behavior;
- whether untrusted archives or a custom `--codex-home` are involved.

The installer validates before writing, rejects unsafe archive members, uses a
per-pet lock, and keeps recoverable backups. These controls reduce risk but do
not replace normal review of files downloaded from untrusted sources.
