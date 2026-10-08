# Contributing

Development uses [uv](https://docs.astral.sh/uv/): `uv sync`, then `uv run pytest`.

The open work queue lives in [`roadmap/`](roadmap/README.md) and is kept by the
[roadmap skill](https://github.com/carby/simple-agentic-roadmap-skill) **v1.0.0**.
Install it into the repo so an agent working here can file, move and close items:

```bash
git clone --branch v1.0.0 https://github.com/carby/simple-agentic-roadmap-skill.git .claude/skills/roadmap
```

`.claude/` is gitignored, so this is a per-clone step. Don't run the skill's `init`:
the roadmap is already set up, and the test suite checks it through the committed
copy of the skill's script, `tools/roadmap.py`, so CI needs no install. To upgrade,
check out the new tag and copy its `scripts/roadmap.py` over `tools/roadmap.py` in
the same commit.
