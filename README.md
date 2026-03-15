# Anamnesis MCP

> *"Learning is not acquiring new knowledge. It is recollecting what was already known."*  
> — Plato

**Anamnesis** is a Model Context Protocol (MCP) server that gives AI coding agents persistent, traceable memory across all your projects and sessions.

Not summaries. Not lossy compression. Cue-pointer records that link back to the full original context — the conversations, decisions, and breakthroughs you already had — so your agent can recollect them when they matter.

---

## The Problem

Every AI agent session starts cold. Your agent has no memory of:

- The Lambda cold-start issue you debugged together last week
- The architectural decision you made in a different project that applies here
- The pattern that worked in CutIndex that would save two hours right now
- The conversation yesterday where you figured out exactly this problem

Claude Code can search your local session files — but it searches blind, without knowing what's inside. What's missing is an **index of meaning**: lightweight cue records that fire when context is similar and point the agent back to the full original artifact.

That is Anamnesis.

---

## How It Works

Anamnesis does not store summaries of your conversations. It stores **cue vectors that point at full traceable artifacts**.

```
Memory record = {
  cue_vector:    embedding of "what this context felt like"
  context_tags:  ["aws-lambda", "cold-start", "python", "2026-03"]
  project:       "CutIndex"
  artifact_type: "conversation" | "diff" | "trace" | "decision"
  artifact_ptr:  path to full original → ~/.claude/sessions/uuid.jsonl
  outcome:       "solved" | "eureka" | "abandoned" | "partial"
  summary:       "Solved Lambda cold-start by increasing reserved concurrency"
}
```

The vector is not the memory. The vector is the trigger that tells the agent *where to look*. The full conversation is preserved, untouched, on your machine.

When similar context fires in a new session, Anamnesis surfaces the cue and fetches the original artifact. The agent recollects — it does not guess.

---

## The Memory SDLC

Memories in Anamnesis go through a lightweight review process before they become trusted context — exactly like code changes go through a PR review before they merge.

```
Agent detects significant event (Eureka, decision, pattern)
  → writes proposed memory to pending/ queue

Reviewer agent scans pending/ (scheduled or on-demand)
  → checks for secrets, evaluates quality, flags duplicates
  → proposes accept / modify / reject

Human reviews (one-click in most cases)
  → accepts → memory promoted to confirmed/ store
  → rejects → discarded

Periodic maintenance agent
  → scans confirmed/ for staleness and redaction needs
```

This means Anamnesis memories are **earned, not automatic**. The confirmed store is a curated record of what you and your agent have genuinely learned together — not a dump of everything that was ever said.

---

## Security: The Moral Compass

Agents encounter secrets in conversation. Anamnesis strips them before they reach the memory store.

Fast redaction runs at write time using pattern matching:

```python
REDACT_PATTERNS = [
    r"(api_key|secret|password|token|credential)\s*[=:]\s*\S+",
    r"[A-Za-z0-9+/]{40,}={0,2}",   # base64 blobs
    r"[0-9a-f]{32,}",               # hex keys
    r"aws_\w+\s*=\s*\S+",           # AWS credentials
    r"(sk|pk|rk)[-_][a-zA-Z0-9]{20,}",  # API key prefixes
]
```

Deeper LLM-assisted redaction runs periodically against the confirmed store. The agent's standing instruction in any JARVIS.md or AGENTS.md configuration is explicit: *store the shape of what happened, never the values.*

---

## MCP Tools

| Tool | Description |
|---|---|
| `anamnesis_recall` | Primary read tool. Called at session start or when context feels familiar. Searches confirmed memories by cue similarity. Returns matched summaries and optionally fetches full artifacts. |
| `anamnesis_remember` | Primary write tool. Called when the agent solves something significant, recognises a pattern, or makes a non-obvious decision. Writes to pending queue for review. |
| `anamnesis_search` | Lightweight keyword + tag search. Faster than recall for when you know what you're looking for. |
| `anamnesis_review` | Returns pending memory queue for human review. |
| `anamnesis_confirm` | Human accepts, rejects, or edits a pending memory. |
| `anamnesis_stats` | Usage overview: memories by project, by outcome, recent activity, top tags. |

### Tool Descriptions (Engineered for Agent Triggering)

The descriptions below are crafted so that a properly configured agent reaches for the right tool at the right moment — not only when explicitly instructed.

**`anamnesis_recall`**
> Use this tool at the start of any non-trivial problem, and whenever the current context feels familiar — a similar error, a similar architecture pattern, a similar library issue. This is your long-term memory across all projects. Do not rely only on training data when you may have directly relevant experience stored here.

**`anamnesis_remember`**
> Use this tool when you solve something that took real effort, discover a pattern that wasn't obvious, make an architectural decision with non-obvious reasoning, or find a fix that contradicted what documentation said. Do not use for routine work. Set eureka_flag=true if this is something the broader developer community would benefit from knowing.

---

## Installation

### Requirements
- Python 3.11+
- `uv` (recommended) or `pip`
- OpenAI API key (for remote embeddings) OR Ollama running locally (for private local embeddings)

### Install

```bash
# Via uv (recommended)
uv tool install anamnesis-mcp

# Via pip
pip install anamnesis-mcp
```

### Configure in Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "anamnesis": {
      "command": "uvx",
      "args": ["anamnesis-mcp"],
      "env": {
        "EMBEDDING_MODEL": "text-embedding-3-small",
        "OPENAI_API_KEY": "sk-...",
        "ANAMNESIS_STORE": "~/.anamnesis"
      }
    }
  }
}
```

### Configure in GitHub Copilot (.agent.md)

Create `~/.config/github-copilot/agents/jarvis.agent.md`:

```markdown
---
name: jarvis
description: Personal developer context engine with persistent memory
tools:
  - anamnesis_recall
  - anamnesis_remember
  - anamnesis_search
---

You are a persistent developer assistant with access to long-term memory
across all projects via Anamnesis.

Before starting any non-trivial problem, call anamnesis_recall with the
current context. When you solve something significant or discover a
non-obvious pattern, call anamnesis_remember. Never store secrets,
credentials, or proprietary business logic in memories.
```

---

## File Structure

```
~/.anamnesis/
├── config.json          # Embedding model, API keys, optional AIOverflow connection
├── memories.db          # SQLite — all memory records and cue vectors
├── artifacts/           # Full original artifacts (Markdown, preserved verbatim)
│   ├── [uuid].md
│   └── ...
├── pending/             # Memory PRs awaiting human review
│   ├── [uuid].json
│   └── ...
└── exports/             # Human-readable exports
```

All data is local. Nothing leaves your machine unless you configure a hosted sync (see Roadmap).

---

## Roadmap

### Phase 1 — Core MCP (current)
- [x] Repo setup and BUSL 1.1 licence
- [ ] SQLite memory store with cue-pointer schema
- [ ] Embedding pipeline (remote: OpenAI, local: Ollama/nomic-embed-text)
- [ ] `anamnesis_recall` tool with cue similarity search
- [ ] `anamnesis_remember` tool with redaction at write time
- [ ] `anamnesis_search` keyword + tag search
- [ ] Memory SDLC: pending → review → confirmed lifecycle
- [ ] `anamnesis_review` and `anamnesis_confirm` tools
- [ ] Claude Code session ingestion (`~/.claude/` JSONL parser)
- [ ] CLI review interface (Rich terminal UI)
- [ ] PyPI publish as `anamnesis-mcp`
- [ ] Submit to MCP registries (mcp.so, pulsemcp.com, awesome-mcp-servers)

### Phase 2 — Enriched Sources
- [ ] claude.ai conversation export ingestion (JSON dump parser)
- [ ] Git diff and commit message ingestion
- [ ] Local Ollama embedding support (fully private, no API cost)
- [ ] `anamnesis_stats` tool
- [ ] Web review UI (lightweight local server)
- [ ] Periodic maintenance agent (staleness detection, deep redaction)

### Phase 3 — Hosted Sync
- [ ] Encrypted cloud sync across devices (hosted service, commercial licence)
- [ ] Team/shared memory namespace
- [ ] AIOverflow MCP integration (Eureka flag → community post draft)
- [ ] Cross-device review interface

---

## Architecture

### The Cue-Pointer Record (Schema)

```python
@dataclass
class MemoryRecord:
    id: str                    # UUID
    cue_vector: list[float]    # 1536-dim embedding (text-embedding-3-small)
                               # or 768-dim (nomic-embed-text local)
    context_tags: list[str]    # Technology and domain tags
    project: str               # Project name (auto-detected from cwd)
    project_path: str          # Absolute path to project root
    artifact_type: str         # conversation | diff | trace | decision | note
    artifact_ptr: str          # Pointer to full original artifact
    summary: str               # 1-3 sentences, human-readable, no secrets
    outcome: str               # solved | eureka | abandoned | partial
    eureka_flag: bool          # True = community-worthy, triggers AIOverflow draft
    status: str                # pending | confirmed | archived
    redacted: bool             # True if redaction was applied
    created_at: datetime
    confirmed_at: datetime | None
```

### Artifact Pointer Format

```
file:///home/user/.anamnesis/artifacts/uuid.md   # stored locally
claude-code:///session/uuid                       # Claude Code JSONL session
git:///path/to/repo@commitHash                    # git commit reference
aioverflow:///post/id                             # published community post
```

### Tech Stack

| Component | Choice | Rationale |
|---|---|---|
| MCP server | Python + FastMCP | Fastest to build, native to Claude Code ecosystem |
| Memory store | SQLite + sqlite-vss | Zero dependencies, local-first, portable |
| Remote embeddings | OpenAI text-embedding-3-small | $0.02/million tokens — effectively free |
| Local embeddings | nomic-embed-text via Ollama | Fully private, no API cost |
| Vector search | sqlite-vss or numpy cosine | Lightweight, no external DB required |
| Redaction | Python regex + scheduled LLM pass | Fast at write time, deep on schedule |
| CLI | Rich (Python) | Clean terminal UI for memory review |

---

## Licence

Anamnesis MCP is licensed under the **Business Source License 1.1 (BUSL-1.1)**.

**You may:**
- Use Anamnesis freely for personal use and development
- Self-host Anamnesis for non-commercial purposes
- Read, modify, and contribute to the source code
- Use Anamnesis internally within your organisation

**You may not (without a commercial licence):**
- Offer Anamnesis as a hosted or managed service to third parties
- Embed Anamnesis in a commercial product you sell or license to others
- Use Anamnesis to build a competing offering

**Change Date:** 2030-03-15  
**Change License:** Apache License 2.0

After the Change Date, this software will be available under Apache 2.0.

For commercial licensing enquiries: [contact details]

See [LICENSE](./LICENSE) for full terms.

---

## Why "Anamnesis"?

In Platonic philosophy, *anamnesis* is the doctrine that learning is not the acquisition of new knowledge but the **recollection of what the soul already knew**. The knowledge was always there — it needed only the right context to surface it.

Your agent already spoke to you about this. The conversation happened. The solution was found. Anamnesis gives it back.

---

## Contributing

Contributions are welcome under the BUSL terms above. Please open an issue before submitting a PR for significant changes.

A Contributor Licence Agreement (CLA) will be required for contributions — this is standard practice for BUSL projects and protects both contributors and the project. Details in [CONTRIBUTING.md](./CONTRIBUTING.md) (coming soon).

---

*Built by [Arek Kulpa](https://github.com/[username]) · Part of the [SDLC.AI](https://github.com/[username]) developer tooling ecosystem*
