# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Youtube Shorts Knowledge** — a project for creating, managing, or processing YouTube Shorts content/knowledge. This project is in early setup (no source code yet).

## bkit Framework

This project uses **bkit v1.6.1** (Vibecoding Kit) for structured development:

- Level: **Dynamic** (fullstack with backend)
- PDCA state: `.bkit/state/pdca-status.json`
- Session memory: `.bkit/state/memory.json`

### Key bkit Workflows

- Start a feature: `/pdca plan {feature}`
- Design phase: `/pdca design {feature}`
- Gap analysis: `/pdca analyze {feature}`
- Completion report: `/pdca report {feature}`

### Development Pipeline

Follow the 9-phase pipeline (`/development-pipeline`):
1. Schema → 2. Convention → 3. Mockup → 4. API → 5. Design System → 6. UI Integration → 7. SEO/Security → 8. Review → 9. Deployment
