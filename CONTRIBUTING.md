# Contributing to BSC DLP Community

Contributions are welcome.

## Principles

1. Do not log or persist raw sensitive values when a masked value or fingerprint is sufficient.
2. New blocking/enforcement features must fail safely and must never report an action as blocked unless the operating system action actually succeeded.
3. Keep platform-specific code behind Go build tags (`*_windows.go`, `*_linux.go`).
4. Add tests for new classifiers and policy behavior.
5. Keep administrator APIs authenticated; agent credentials must never grant console access.
6. Network-exposed deployments must document TLS/reverse-proxy requirements.

## Local development

Windows contributors can double-click `START-BSC-DLP.cmd`. Source mode bootstraps a private Python virtual environment and builds the Go agent when the required toolchains are present.

The prebuilt GitHub release does not require Python or Go on the end-user machine.
