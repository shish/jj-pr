# JJ PR GitHub Integration

- assumes `gh` is installed and configured
- assumes your git remote is set to `https://github.com/<user>/<repo>` or `git@github.com:<user>/<repo>.git`
- assumes you already have authentication configured for push & pull
- uses github stacks, which are honestly not great
  - doesn't support cross-repo PRs
  - requires deleting and re-creating stacks for all but the most trivial changes
  - creates a branch for every commit
