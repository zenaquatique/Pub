# Graph Report - /home/user/Pub  (2026-04-23)

## Corpus Check
- Corpus is ~772 words - fits in a single context window. You may not need a graph.

## Summary
- 39 nodes · 59 edges · 9 communities detected
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 6 edges (avg confidence: 0.77)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Platform & Ecosystem|Platform & Ecosystem]]
- [[_COMMUNITY_Core Workflow Skills|Core Workflow Skills]]
- [[_COMMUNITY_Hard Gates & TDD|Hard Gates & TDD]]
- [[_COMMUNITY_Subagent Architecture|Subagent Architecture]]
- [[_COMMUNITY_Skill-First Discipline|Skill-First Discipline]]
- [[_COMMUNITY_Evidence & Debugging|Evidence & Debugging]]
- [[_COMMUNITY_Code Review|Code Review]]
- [[_COMMUNITY_Human Partner Model|Human Partner Model]]
- [[_COMMUNITY_Repository Root|Repository Root]]

## God Nodes (most connected - your core abstractions)
1. `Superpowers Agentic Skills Framework` - 33 edges
2. `Superpowers Core Development Workflow` - 11 edges
3. `Hard Gates Design Principle` - 5 edges
4. `Subagent Isolation Design Principle` - 5 edges
5. `subagent-driven-development Skill` - 4 edges
6. `verification-before-completion Skill` - 4 edges
7. `using-superpowers Skill` - 3 edges
8. `brainstorming Skill` - 3 edges
9. `dispatching-parallel-agents Skill` - 3 edges
10. `test-driven-development Skill` - 3 edges

## Surprising Connections (you probably didn't know these)
- `Superpowers Agentic Skills Framework` --conceptually_related_to--> `using-superpowers Skill`  [EXTRACTED]
  docs/superpowers/specs/2026-04-23-explore-superpowers-analysis.md → docs/superpowers/specs/2026-04-23-explore-superpowers-analysis.md  _Bridges community 0 → community 1_
- `Superpowers Agentic Skills Framework` --conceptually_related_to--> `brainstorming Skill`  [EXTRACTED]
  docs/superpowers/specs/2026-04-23-explore-superpowers-analysis.md → docs/superpowers/specs/2026-04-23-explore-superpowers-analysis.md  _Bridges community 0 → community 2_
- `Superpowers Agentic Skills Framework` --conceptually_related_to--> `subagent-driven-development Skill`  [EXTRACTED]
  docs/superpowers/specs/2026-04-23-explore-superpowers-analysis.md → docs/superpowers/specs/2026-04-23-explore-superpowers-analysis.md  _Bridges community 0 → community 3_
- `Superpowers Agentic Skills Framework` --conceptually_related_to--> `systematic-debugging Skill`  [EXTRACTED]
  docs/superpowers/specs/2026-04-23-explore-superpowers-analysis.md → docs/superpowers/specs/2026-04-23-explore-superpowers-analysis.md  _Bridges community 0 → community 5_
- `Superpowers Agentic Skills Framework` --conceptually_related_to--> `requesting-code-review Skill`  [EXTRACTED]
  docs/superpowers/specs/2026-04-23-explore-superpowers-analysis.md → docs/superpowers/specs/2026-04-23-explore-superpowers-analysis.md  _Bridges community 0 → community 6_

## Hyperedges (group relationships)
- **Parallel and Sequential Execution Skill Triad** — skill_subagent_driven_development, skill_executing_plans, skill_dispatching_parallel_agents [EXTRACTED 0.90]
- **TDD, Code Review and Verification Quality Cycle** — skill_test_driven_development, skill_requesting_code_review, skill_verification_before_completion [INFERRED 0.82]
- **Design Brainstorming Hard-Gate Workflow** — skill_brainstorming, concept_hard_gate_element, principle_hard_gates [EXTRACTED 0.88]

## Communities

### Community 0 - "Platform & Ecosystem"
Cohesion: 0.18
Nodes (11): Superpowers Agentic Skills Framework, Zero Dependency Constraint, Claude Code Platform, Cursor Platform, Gemini CLI Platform, GitHub Copilot CLI Platform, OpenAI Codex CLI Platform, OpenCode Platform (+3 more)

### Community 1 - "Core Workflow Skills"
Cohesion: 0.29
Nodes (7): Superpowers Core Development Workflow, YAML Frontmatter Skill Structure, executing-plans Skill, finishing-a-development-branch Skill, using-git-worktrees Skill, using-superpowers Skill, writing-plans Skill

### Community 2 - "Hard Gates & TDD"
Cohesion: 0.4
Nodes (5): HARD-GATE Skill Element, Hard Gates Design Principle, Rationale: Hard Gates Block Premature Implementation, brainstorming Skill, test-driven-development Skill

### Community 3 - "Subagent Architecture"
Cohesion: 0.5
Nodes (5): SUBAGENT-STOP Skill Element, Subagent Isolation Design Principle, Rationale: Fresh Agents Per Task Prevent Context Drift, dispatching-parallel-agents Skill, subagent-driven-development Skill

### Community 4 - "Skill-First Discipline"
Cohesion: 0.67
Nodes (3): Process Over Improvisation Design Principle, Skill-First Discipline Design Principle, Rationale: Skill-First Discipline Prevents Ad-Hoc Action

### Community 5 - "Evidence & Debugging"
Cohesion: 0.67
Nodes (3): Evidence Over Claims Design Principle, systematic-debugging Skill, verification-before-completion Skill

### Community 6 - "Code Review"
Cohesion: 1.0
Nodes (2): receiving-code-review Skill, requesting-code-review Skill

### Community 7 - "Human Partner Model"
Cohesion: 1.0
Nodes (2): Human Partner Model Design Principle, Rationale: Human Partner Framing Establishes Duty of Care

### Community 8 - "Repository Root"
Cohesion: 1.0
Nodes (1): Pub Repository README

## Knowledge Gaps
- **15 isolated node(s):** `Pub Repository README`, `Superpowers Repository Exploration Analysis`, `writing-skills Skill`, `YAGNI Ruthlessly Design Principle`, `Claude Code Platform` (+10 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Code Review`** (2 nodes): `receiving-code-review Skill`, `requesting-code-review Skill`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Human Partner Model`** (2 nodes): `Human Partner Model Design Principle`, `Rationale: Human Partner Framing Establishes Duty of Care`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Repository Root`** (1 nodes): `Pub Repository README`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Superpowers Agentic Skills Framework` connect `Platform & Ecosystem` to `Core Workflow Skills`, `Hard Gates & TDD`, `Subagent Architecture`, `Skill-First Discipline`, `Evidence & Debugging`, `Code Review`, `Human Partner Model`?**
  _High betweenness centrality (0.858) - this node is a cross-community bridge._
- **Why does `Hard Gates Design Principle` connect `Hard Gates & TDD` to `Platform & Ecosystem`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Why does `Subagent Isolation Design Principle` connect `Subagent Architecture` to `Platform & Ecosystem`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Subagent Isolation Design Principle` (e.g. with `dispatching-parallel-agents Skill` and `SUBAGENT-STOP Skill Element`) actually correct?**
  _`Subagent Isolation Design Principle` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Pub Repository README`, `Superpowers Repository Exploration Analysis`, `writing-skills Skill` to the rest of the system?**
  _15 weakly-connected nodes found - possible documentation gaps or missing edges._