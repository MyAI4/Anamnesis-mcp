# Anamnesis MCP — Next Steps

## Immediate (Today)

### 1. Complete the repo setup
- [ ] Add the README.md (paste from this doc set)
- [ ] Add LICENSE file manually — BUSL 1.1 with your details filled in:
  - Licensor: Arek Kulpa
  - Licensed Work: Anamnesis MCP
  - Change Date: 2030-03-15
  - Change License: Apache License 2.0
  - Additional Use Grant: (use the wording from README)
- [ ] Add .gitignore (Python standard)
- [ ] Add CONTRIBUTING.md placeholder (one paragraph, CLA note)

BUSL 1.1 full text source: https://mariadb.com/bsl11/
Fill in the Parameters section at the top — everything else is boilerplate.

---

### 2. Repo structure to create
```
anamnesis-mcp/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── pyproject.toml
├── src/
│   └── anamnesis_mcp/
│       ├── __init__.py
│       ├── server.py          ← FastMCP server, tool definitions
│       ├── store.py           ← SQLite memory store
│       ├── embeddings.py      ← embedding pipeline (remote + local)
│       ├── ingest/
│       │   ├── claude_code.py ← ~/.claude/ JSONL parser
│       │   └── export.py      ← claude.ai JSON export parser
│       ├── redaction.py       ← secret stripping at write time
│       ├── review.py          ← CLI review interface (Rich)
│       └── models.py          ← MemoryRecord dataclass
├── tests/
│   ├── test_store.py
│   ├── test_embeddings.py
│   └── test_redaction.py
└── docs/
    └── architecture.md
```

---

## This Week — Build Sprint 1

### Goal: Working recall + remember tools against your own Claude Code sessions

**Day 1: Foundation**
- Set up pyproject.toml with FastMCP, sqlite-utils, openai dependencies
- Implement MemoryRecord dataclass (models.py)
- Create SQLite schema (store.py) — memories table + pending table
- Basic CRUD operations

**Day 2: Ingestion**
- Write Claude Code session parser (ingest/claude_code.py)
  - Reads ~/.claude/projects/*/conversations/*.jsonl
  - Segments long conversations by topic drift (sliding window embedding comparison)
  - Creates MemoryRecord proposals for each significant segment
- Test against your actual local sessions

**Day 3: Embeddings + Recall**
- Implement embedding pipeline (embeddings.py)
  - Remote: OpenAI text-embedding-3-small
  - Local stub: nomic-embed-text placeholder for Phase 2
- Implement cosine similarity search (numpy, no external vector DB yet)
- Wire up anamnesis_recall tool in server.py
- Test: does it surface relevant past sessions when given current context?

**Day 4: Remember + Redaction**
- Implement redaction.py with regex patterns
- Implement anamnesis_remember tool
  - Writes to pending/ queue
  - Runs redaction before storage
  - Returns redaction_warnings if patterns fired
- Basic pending → confirmed promotion (no review UI yet, just CLI command)

**Day 5: Wire it up personally**
- Add to your Claude Code MCP config
- Use it for a real work session
- Note what breaks, what's missing, what's surprisingly good
- Fix the most annoying thing

---

## The Personal Test (Most Important Step)

Before anything else — before PyPI, before marketing, before anything — Anamnesis must pass this test:

> You are implementing a user story. You describe the context to your agent.
> Anamnesis surfaces a memory from three months ago in a different project
> where you solved something structurally identical.
> The agent uses that memory and saves you two hours.

That is the moment that proves this works. Everything else is secondary.

Run this test at the end of Sprint 1. If it works, proceed. If it doesn't, fix it before moving on.

---

## Sprint 2 (Week 2-3) — Memory SDLC + CLI

- [ ] Rich terminal review interface for pending queue
- [ ] anamnesis_review tool (returns pending queue to agent)
- [ ] anamnesis_confirm tool (human accepts/rejects via CLI)
- [ ] Periodic redaction scan of confirmed store
- [ ] anamnesis_stats tool
- [ ] Proper error handling throughout
- [ ] First test suite (pytest)

---

## Sprint 3 (Week 3-4) — Polish + Publish

- [ ] pyproject.toml configured for PyPI publish
- [ ] uv/uvx compatibility (installable via uvx anamnesis-mcp)
- [ ] README finalised with real screenshots/demos
- [ ] Basic docs (architecture.md)
- [ ] Publish to PyPI as anamnesis-mcp
- [ ] Submit PR to awesome-mcp-servers (punkpeye/awesome-mcp-servers)
- [ ] Submit to mcp.so
- [ ] Submit to pulsemcp.com
- [ ] Hacker News Show HN post

---

## The Show HN Post (Draft)

**Title:** Show HN: Anamnesis – cue-pointer memory MCP for AI coding agents

**Body:**
I built an MCP server that gives AI coding agents persistent memory
across projects — not by storing summaries, but by storing lightweight
cue vectors that point back to full original conversation artifacts.

The difference: when similar context fires in a new session, your agent
doesn't get a lossy summary. It gets sent back to the exact conversation
where you worked through this problem three months ago, in a different
project.

Memories go through a review process before they're trusted — proposed
by the agent, confirmed by you, like a PR for knowledge. Secrets are
stripped at write time.

First-class support for Claude Code session files (~/.claude/ JSONL).
Local-first, SQLite, no external services required.

BUSL 1.1 — self-host free, commercial hosting requires a licence.

GitHub: [link]

---

## Key Decisions Still Open

**Embedding model default**
OpenAI text-embedding-3-small is cheapest/easiest for MVP.
Nomic-embed-text (Ollama) for Phase 2 privacy option.
Don't block on this — ship with OpenAI first.

**Topic segmentation algorithm**
Sliding window cosine similarity on consecutive turns is good enough for MVP.
LLM-assisted segmentation is Phase 2. Don't over-engineer this.

**Vector search**
sqlite-vss extension vs pure numpy cosine similarity.
sqlite-vss is cleaner but requires compiled extension.
Start with numpy — works everywhere, zero deps, fast enough for personal use.
Migrate to sqlite-vss in Sprint 3 if performance is an issue.

**Review interface**
CLI first (Rich library). Web UI is Phase 2.
The review queue is small — human reviews maybe 5-10 memories per day.
A terminal table is completely sufficient.

---

## What NOT to Build Yet

- Web UI (Phase 2)
- Team/shared memory (Phase 3 / commercial)
- AIOverflow integration (Phase 3 — AIOverflow doesn't exist yet)
- Cross-device sync (Phase 3 / commercial)
- Local embedding model (Phase 2)
- Memory decay/forgetting curves (Phase 2)
- Semantic clustering of memories (Phase 2)

Resist the urge to build these now. The personal recall test is the only
success criterion for Sprint 1.

---

## Longer Horizon — How This Fits

```
Anamnesis MCP        ← you are here
  └── powers Jarvis  ← personal developer identity layer
        └── feeds AIOverflow  ← community knowledge commons
              └── part of SDLC.AI  ← the full developer process framework
```

Anamnesis is the foundation. Everything else depends on it working well
for you personally before it can serve anyone else.

Ship the smallest thing that passes the personal recall test.
That is Sprint 1.
```
