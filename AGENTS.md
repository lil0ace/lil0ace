# AGENTS.md

Guidance for AI agents working in this repository.

## Repository overview

This is the GitHub **profile README** repository [`lil0ace/lil0ace`](https://github.com/lil0ace/lil0ace). The only tracked source file is `README.md`, which GitHub renders on the user profile. There is no application server, package manager manifest, Docker setup, or automated test/lint configuration in the tree.

## Cursor Cloud specific instructions

### Services

| Service | Required? | Notes |
|---------|-----------|--------|
| Git / GitHub | Optional | Used to edit and push `README.md`; GitHub hosts the rendered profile |
| Local dev servers | No | Nothing to run for normal development |
| Databases / queues | No | N/A |

### Lint, test, and build

There are no project-defined lint, test, or build scripts. Agents can sanity-check changes with:

- `git diff README.md` before commit
- `wc -l README.md` or reading the file to confirm content
- Optional local Markdown preview (e.g. editor preview, or render to HTML with a one-off `pip install --user markdown` — not part of this repo)

Do **not** expect `npm test`, `pytest`, `docker compose up`, or similar unless new tooling is added to the repository.

### Running / demonstrating changes

The product behavior is **profile README display on GitHub**. After pushing to `main`, verify on https://github.com/lil0ace (profile page). Locally, preview is limited to Markdown/HTML preview of `README.md` only.

### Update script behavior

The VM update script is a no-op (`true`) because this repository has no installable dependencies. Future agents should not add heavy install steps to the update script unless the repo gains a real application stack.
