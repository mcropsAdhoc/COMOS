# COMMOS Container Security Exception Register

## Policy
COMMOS CI always produces a full container vulnerability report. The blocking container gate fails on High/Critical vulnerabilities only when an upstream fixed version exists. High/Critical findings with no available fix remain visible and must be reviewed on every release.

## Current inherited exceptions
The Python 3.13 / Debian 13 runtime currently reports several High-severity findings marked by the scanner as "won't fix" or without an available fixed package. These include inherited packages such as:
- glibc
- util-linux
- ncurses
- perl-base
- zlib
- libacl

These are not application dependency vulnerabilities and are not hidden from CI.

## Controls
1. Full Grype report runs on every build.
2. Actionable High/Critical CVEs with fixed versions block CI.
3. pip-audit blocks vulnerable Python dependencies.
4. CodeQL blocks source-level security issues.
5. Secret scanning runs on the current tree.
6. SBOM is generated for every image build.
7. Base image is refreshed regularly.
8. This exception register must be reviewed before every pilot release.

## Exit criteria
An inherited exception is removed when:
- the base image publishes a fixed package, or
- COMMOS moves to a minimal runtime that eliminates the affected package.

For industrial production, prefer a continuously remediated minimal runtime and pin the final image by digest after validation.
