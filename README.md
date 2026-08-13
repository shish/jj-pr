# JJ Forge Integration

(For GitHub, Gerrit, and Phabricator; it should be easy to add more)

# Features

* `jj pr upload` - create or update a code review for each commit in the current branch
* `jj pr rebase` - rebase the current branch on top of its merge target (eg if the PR is based on `main`, rebase on top of `main`; if the PR is based on another PR, rebase on top of that other PR)
* `jj pr list` - list the status of my open PRs/CRs/Diffs
* `jj pr log` - show `jj log` output annotated with review status
* `jj pr pre-commit` - run pre-commit hooks on all commits in the current stack
* `jj pr download <pr/cr/diff>` - download a specific PR/CR/Diff from the forge

![jj pr list output](.github/list-demo.png)

![jj pr log output showing review status](.github/log-demo.png)

## Stability Notice

Right now I'm very much building this for myself, and I haven't settled on exactly what the interface should look like, so parts may change, internally and externally (eg command names).

# Why

Because I'm regularly using github, gerrit, and phabricator, and I don't like any of their standard `git` workflows (and then I go ahead and use `jj`, which has *much* better client-side UX, but the forge integrations are even less-well-supported...)

I really just want `jj pr rebase` to bring me up to date with remote changes, and `jj pr upload` to submit my local changes for review - automatically Doing The Right Thing (eg updating existing reviews vs creating new ones), working consistently across forges.

# Workflow

* `jj pr rebase --all-branches` - start the day by pulling remote changes and rebasing all my local branches on top of them
* `jj pr list` / `jj pr log` - check for any reviews which need attention

## If I want to work on a new feature

* `jj new 'trunk()'` - create a new branch off of trunk (ie, `main` or `master`)
* `vim ...` - make some changes
* `jj commit` - commit the first unit of work
* `vim ...` - make more changes
* `jj commit` - commit the next unit of work
* `jj pr upload` - upload the two commits for review

## If any of my code needs to be changed based on feedback

* `jj edit <change id>` - switch to the change that needs to be fixed
* `vim ...` - make the changes
* `jj pr upload -m 'fixed the bugs'` - upload an updated version of the commit for review, with a comment listing what changed since last time

## If I want to test somebody else's code

* `jj pr download <pr/cr/diff>` - download a specific PR/CR/Diff from the forge

# Backend Notes

Backend will be automatically detected based on the git remote URL; if that doesn't work, you can set the backend explicitly with `jj config set --repo pr.forge <backend>`.
 
* [github](./src/jjpr/forges/github/README.md)
* [gerrit](./src/jjpr/forges/gerrit/README.md)
* [phabricator](./src/jjpr/forges/phabricator/README.md)

# Install

```sh
git clone https://github.com/shish/jj-pr
cd jj-pr
uv sync
jj config set --user aliases.pr "['util', 'exec', '--', '$(pwd)/.venv/bin/jj-pr']"
```

# Unit Testing

* Tests for module `foo.py` live in `foo_test.py` next to it
* The `demo` forge contains some hard-coded synthetic data to be able to test eg "print a list of open CRs" without needing to talk to a real forge
* Fixtures live in `conftest.py`
  * Top level conftest contains fixtures for eg:
    * Creating a mock `$HOME` with pre-configured config files
    * Creating a git repo in `/tmp`, cloning it, cd'ing into it
  * Backend-specific conftest files contain integration-test fixtures for eg:
    * Authenticating with a real forge
    * Creating a test repo with a randomly generated name
    * Pre-populating the test repo
    * Cloning the repo, cd'ing into it
    * Cleaning up the test repo from the forge after testing is complete
* `jj.diagram()` can be useful to asssert the state of the repo before and after a given command

```bash
uv run pytest        # full test suite
uv run ruff format   # formatting
uv run ruff check    # linting
uv run ty check      # type checking
uv run prek install  # install pre-commit hook to automatically run checks
```

# Integration Testing

Integration tests will run iff `JJPR_TEST_<FORGE>_*` variables are set

```bash
docker compose up -d
docker compose ps    # wait and repeat until containers are healthy

# Create admin user, get a token from settings
open "http://gerrit.localhost:8080/settings/#HTTPCredentials"
export JJPR_TEST_GERRIT_API_TOKEN=...

# Create admin user, get a token from settings
open "http://phab.localhost:8081/settings/user/admin/page/apitokens/"
export JJPR_TEST_PHABRICATOR_API_TOKEN=...
open "http://phab.localhost:8081/settings/user/admin/page/vcspassword/"
export JJPR_TEST_PHABRICATOR_VCS_PASSWORD=...

# Run just the integration tests for a specific forge
uv run pytest -m "integration and gerrit"

# Run all the integration tests
uv run pytest -m integration

# Delete test environment
docker compose down -v
```

# Terminology

Making a table because terminology is inconsistent (and occasionally mutually-exclusive) across forges. See sapling using "submit" to mean "upload to be reviewed" while gerrit uses "submit" to mean "merge into main branch", which can have dangerous and difficult to undo consequences if you mix them up...

| Concept | JJ-PR | Sapling | GitHub | Gerrit | Phabricator |
| ------- | ----- | ------- | ------ | ------ | ----------  |
| Unit of work | change | commit | commit | change | diff | change |
| Unit of review | branch / change | - | branch | change | revision | branch / change |
| Send for review | `jj pr upload` | `sl pr submit` | `gh pr create` | `git push` | `arc diff` |
| Check code to be reviewed | `jj pr download` | `sl pr pull` | `gh pr checkout` | `git fetch` | `arc patch` |
| Merge reviewed code | - | - | `gh pr merge`, `--rebase` / `--squash` / `--merge` flags | "submit" button (server-side rebase) | `arc land` (client-side rebase) |
| List open reviews | `jj pr list ` | `sl pr list` | `gh pr list` | - | `arc list` |
| Log with review status | `jj pr log` | `sl ssl` | - | - | - |
| CI/CD status | Checks | - | Checks | Checks | Builds |
| Merge Blockers | Blockers | - | Required Checks, Required Reviews | Submit Requirements | - |
