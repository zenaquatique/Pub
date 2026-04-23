# Superpowers Repository Exploration

**Date:** 2026-04-23  
**Branch:** claude/explore-superpowers-Bgcj3  
**Source:** https://github.com/obra/superpowers

## Overview

This document captures the findings from an exploration of the obra/superpowers repository — an agentic skills framework and software development methodology for coding agents (Claude Code, Codex, Cursor, Gemini CLI, GitHub Copilot CLI).

## Repository Structure

```
superpowers/
├── skills/                  # 14 composable skill modules
├── agents/                  # Agent-specific config overlays
├── commands/                # CLI command definitions
├── docs/                    # Specs, plans, and platform docs
├── hooks/                   # Session lifecycle hooks
├── scripts/                 # Tooling (sync, release, etc.)
├── tests/                   # Test suite
├── .claude-plugin/          # Claude Code plugin manifest
├── .codex/                  # OpenAI Codex plugin files
├── .cursor-plugin/          # Cursor plugin files
├── .opencode/               # OpenCode install instructions
├── CLAUDE.md                # AI-agent contributor guidelines
├── AGENTS.md                # OpenAI Codex agent instructions
├── GEMINI.md                # Gemini CLI agent instructions
└── README.md                # Installation and workflow docs
```

## Skills Inventory

| Skill | Category | Description |
|-------|----------|-------------|
| `using-superpowers` | Meta | Entry point — establishes skill-first discipline before any response |
| `brainstorming` | Collaboration | Socratic design refinement before any implementation |
| `writing-plans` | Collaboration | Breaks approved designs into 2-5 min tasks with exact specs |
| `subagent-driven-development` | Execution | Fresh subagent per task with two-stage review |
| `executing-plans` | Execution | Batch execution with human checkpoints |
| `dispatching-parallel-agents` | Execution | Concurrent subagent workflows for independent tasks |
| `test-driven-development` | Testing | Enforces RED-GREEN-REFACTOR; deletes code written before tests |
| `systematic-debugging` | Debugging | 4-phase root cause process before proposing any fix |
| `verification-before-completion` | Debugging | Evidence-based verification before claiming success |
| `using-git-worktrees` | Infrastructure | Isolated workspaces per feature branch |
| `requesting-code-review` | Review | Pre-review checklist before committing/merging |
| `receiving-code-review` | Review | Technical rigor when responding to review feedback |
| `finishing-a-development-branch` | Lifecycle | Structured merge/PR/keep/discard decision workflow |
| `writing-skills` | Meta | How to create and test new skills for the framework |

## Core Workflow

```
User message
     ↓
using-superpowers  (check for applicable skills first, always)
     ↓
brainstorming      (explore intent → design → spec doc → commit)
     ↓
using-git-worktrees (isolated branch + verify clean baseline)
     ↓
writing-plans      (2-5 min tasks, exact file paths + code)
     ↓
subagent-driven-development / executing-plans
  ↓ (each task)
  test-driven-development   (RED-GREEN-REFACTOR)
  requesting-code-review    (after each task)
     ↓
verification-before-completion
     ↓
finishing-a-development-branch (merge/PR/cleanup)
```

## Design Principles

- **Skill-first discipline**: Every response must check for applicable skills before acting, even clarifying questions.
- **Hard gates**: brainstorming blocks all implementation until design is approved; TDD blocks implementation until a failing test exists.
- **Evidence over claims**: `verification-before-completion` requires running actual commands and reading output — no assertions without proof.
- **YAGNI ruthlessly**: All design phases actively prune unrequested features.
- **Process over improvisation**: Skills are mandatory workflows, not suggestions. The framework treats ad-hoc action as the failure mode.
- **Subagent isolation**: Fresh agents per task prevent context drift over long sessions.
- **Human partner model**: The framework uses "human partner" (not "user") as a deliberate design choice that frames the agent's duty of care.

## Platform Support

The framework ships as a plugin/extension for:
- **Claude Code** — official marketplace (`/plugin install superpowers@claude-plugins-official`)
- **OpenAI Codex CLI / App** — via plugin search
- **Cursor** — via `/add-plugin superpowers`
- **OpenCode** — via install instructions URL
- **GitHub Copilot CLI** — via marketplace
- **Gemini CLI** — via `gemini extensions install`

## Skill Architecture Notes

Skills are structured markdown files with YAML frontmatter (`name`, `description`). The description field drives auto-invocation — agents match task context against descriptions. Skills use structured elements:
- `<HARD-GATE>` — blocks proceeding until condition met
- `<SUBAGENT-STOP>` — skips the skill when dispatched as a subagent
- `<EXTREMELY-IMPORTANT>` — emphasis for behavior-shaping instructions
- Numbered checklists map to `TodoWrite` tasks
- Graphviz dot diagrams describe process flow

## Contributing Constraints

The project has a 94% PR rejection rate. Key constraints:
- No third-party dependencies (zero-dependency by design)
- Skill changes require before/after eval results
- No domain-specific or project-specific skills in core
- Each PR must address one real, experienced problem
- AI agents must show the complete diff to their human partner before submitting

## Key Files for New Contributors

| File | Purpose |
|------|--------|
| `skills/using-superpowers/SKILL.md` | How skills are invoked and prioritized |
| `skills/writing-skills/SKILL.md` | How to create and test new skills |
| `skills/brainstorming/SKILL.md` | Full brainstorming process with checklist |
| `CLAUDE.md` | AI-agent contributor guidelines (read before any PR) |
| `.github/PULL_REQUEST_TEMPLATE.md` | Required PR template |
| `docs/superpowers/specs/` | Existing design documents as reference |
