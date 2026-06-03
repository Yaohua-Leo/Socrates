# Socrates

Socrates is a local-first Python CLI skeleton for project-based mathematics
learning. The current implementation focuses on Phase 0: creating a stable
learning-project directory layout and writing initial state files.

## Quick Start

```powershell
python -m socrates init --topic "Group Theory" --path ".\projects\group_theory" --goal "Prepare for representation theory."
```

The command creates a Socrates learning project with metadata, reference,
planning, session, note, exercise, knowledge-base, export, and evaluation
directories.

## Development

Run the local checks:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check.ps1
```

The long-term development target and phased roadmap are stored in `docs/`.
