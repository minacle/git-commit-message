# git-commit-message

Staged changes -> GPT commit message generator.

## Install (editable)

```fish
python -m pip install -e .
```

## Usage

- Print commit message only:

```fish
git add -A
git-commit-message "optional extra context about the change"
```

- Force single-line subject only:

```fish
git-commit-message --one-line "optional context"
```

- Limit subject length (default 72):

```fish
git-commit-message --one-line --max-length 50 "optional context"
```

- Commit immediately with editor:

```fish
git-commit-message --commit --edit "refactor parser for speed"
```

Environment:

- `OPENAI_API_KEY`: required
- `GIT_COMMIT_MESSAGE_MODEL` or `OPENAI_MODEL`: optional (default: `gpt-5-mini`)
