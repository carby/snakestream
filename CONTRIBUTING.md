# Contributing

Development uses [uv](https://docs.astral.sh/uv/): `uv sync`, then `uv run pytest`.

The open work queue lives in [`roadmap/`](roadmap/README.md) and is kept by the
[roadmap skill](https://github.com/carby/simple-agentic-roadmap-skill), whose
release is pinned by `version` in `roadmap/roadmap.toml`. It needs Node 22 or
later. Install the CLI once per machine, then the skill into the repo so an agent
working here can file, move and close items:

```bash
npm install -g simple-agentic-roadmap-skill
roadmap update --tools claude
```

`.claude/` is gitignored, so the second step is per clone. Don't run `init`: the
roadmap is already set up. `tests/test_roadmap.py` runs `roadmap check` at the
pinned release through `npx`, so the test suite needs Node too; without `npx`
it skips that test locally and fails it in CI. To upgrade, install the new
release globally and run `roadmap update`, which moves the pin and refreshes
the skill; commit the result.
