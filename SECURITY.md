# Security Policy

## Reporting Security Issues

The Mandala team takes the security of our deterministic kernel confinement and policy governance systems seriously. We welcome responsible disclosure from security researchers and auditors.

If you believe you have discovered a vulnerability in Mandala (including sandbox escapes, capability bypasses, or receipt forgery):

1. **Do not open a public GitHub issue.**
2. Send a detailed report via email to: `security@whitemagic.dev`.
3. Include the following information:
   - Component affected (`gate-lite`, `MANDALAOS_SOVEREIGN`, or `LAKSHMI`).
   - Detailed description of the vulnerability and expected vs. actual confinement behavior.
   - Minimal reproducible proof-of-concept (PoC) script or test case.
   - System environment (Linux kernel version, Landlock ABI version, distribution).

We will acknowledge receipt of your vulnerability report within 48 hours and provide regular updates until resolution.

## Scope

Security-critical boundaries include:
* **Kernel Confinement**: Integrity of Linux Landlock LSM rules and Bubblewrap namespace boundaries (`MANDALAOS_SOVEREIGN`).
* **Execution Authority**: Enforcement of task preflight capability checks and authority envelope validation (`gate-lite`).
* **Provenance Verification**: Resistance to tampering or forgery of offline continuity receipts (`continuity-receipt` standard).

## Release Verification

Official release tags and manifest digests are signed with our release-signing key. Verify signatures using standard OpenSSH or GPG tooling:
```bash
git verify-tag <tag_name>
```
