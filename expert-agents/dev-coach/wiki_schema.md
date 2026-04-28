# Dev Coach Wiki Schema

This wiki accumulates knowledge about the developer's technical work across sessions.

## What to Track

- **Technical decisions** — architectural choices, library selections, tradeoffs considered
- **Recurring problems** — issues that come up repeatedly and how they were resolved
- **Patterns observed** — coding patterns, testing approaches, workflows the developer favours
- **Tech choices** — frameworks, tools, languages, and why they were chosen

## What NOT to Track

- Generic advice or coaching not specific to this developer's work
- Temporary context that won't be relevant in future sessions
- Session mechanics (connection issues, audio problems, etc.)

## Page Naming Conventions

- `decisions-<topic>.md` — for architectural or technical decisions
- `patterns-<topic>.md` — for observed coding or workflow patterns
- `problems-<topic>.md` — for recurring issues and resolutions
- `tech-<name>.md` — for notes on a specific tool or library

## Index Entry Format

Each entry in index.md should be:
`- [[filename.md]] — one-line summary (last updated: YYYY-MM-DD)`

## Page Format

Each page should start with a `# Title` and include:
- A brief summary
- Key details with dates where relevant
- Cross-references to related pages using `[[filename.md]]`
