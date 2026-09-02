# Cloudflare Pages notes

This repository is markdown, registries, and routing files. It is not an existing frontend. The static site is a generated HTML projection of the public documents already in this repo.

The generator does not invent projects, metrics, or maturity. It does not migrate Python engines or knowledge graphs. It does not enable R2. A live Cloudflare publication is not asserted by this file.

## What is published

Markdown:

- `README.md`
- `AI_FRONT_DOOR.md`
- `PUBLIC_REPO_MAP.md`
- `PORTABILITY_MAP.md`
- `ai/BUILD_PHILOSOPHY.md`
- `ai/AI_PORTFOLIO_TOC.md`
- `ai/SHANNON_INFORMATION_THEORY_FOR_AI_GOVERNANCE.md`
- this file

Copied JSON (source-owned public registries):

- `registry/profile-repo-routing-registry.json`
- `registry/portfolio-capability-evidence.json`
- `registry/portable-workflow-patterns.json`

Operator files such as `AGENTS.md` are left on GitHub.

## Local preview

```text
python3 scripts/build_pages_site.py
python3 -m http.server --directory site 8788
```

Then open `http://127.0.0.1:8788/`.

Pages-faithful local preview, after the same build:

```text
npx wrangler pages dev ./site
```

Rebuild after editing source markdown. Generated files live in `site/` and are not the canonical source.

## Publish to Cloudflare Pages

Wrangler in this agent environment was not authenticated, so no live Pages publication was performed here.

Direct upload from a machine that can run `wrangler login`:

```text
python3 scripts/build_pages_site.py
npx wrangler pages deploy ./site --project-name=lowelltwong-alt
```

Git-connected Pages (dashboard → Workers & Pages → Create → Pages → Import repository):

| Setting | Value |
|---|---|
| Project name | `lowelltwong-alt` |
| Default git branch | `main` after merge |
| Build command | `python3 scripts/build_pages_site.py` |
| Build output directory | `site` |

`wrangler.jsonc` sets `pages_build_output_dir` to `./site` for the same output folder. There are no bindings.

If a Pages build image lacks Python 3, run the generator locally and set the output directory to a committed `site/` folder. This repo currently gitignores `site/` so the Git-connected path expects Python 3 during the Pages build.
