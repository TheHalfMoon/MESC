# Security Policy

## Scope

MedScale is a research platform that operates on **synthetic data only** and is **not a
medical device**. It must never be used for clinical decision-making. Nonetheless we take
software security and data-boundary integrity seriously.

## Reporting a vulnerability

Please report suspected vulnerabilities **privately**, not via public issues:

- Use GitHub's [private vulnerability reporting](https://github.com/TheHalfMoon/MESC/security/advisories/new), or
- Email **alshehriofficial@gmail.com** with the details and reproduction steps.

We aim to acknowledge reports within **7 days** and to provide a remediation timeline
after triage. Please give us a reasonable window to address the issue before public
disclosure.

## What we consider a security issue

- Any path by which **real patient data / PHI could enter** MedScale training,
  evaluation, or benchmark data (this violates the one-way PHI boundary and is treated as
  a top-severity issue).
- Any mechanism by which MedScale could take a **dependency on Afia** or leak restricted,
  non-permissively-licensed content into the repository.
- Standard software vulnerabilities (code execution, dependency CVEs, supply-chain
  risks in the toolchain).

## What is out of scope

- Clinical accuracy of model outputs (MedScale outputs are not clinically validated by
  design — see every model card).
- Issues that require using MedScale outside its documented, synthetic-only purpose.
