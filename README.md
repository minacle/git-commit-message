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

- Select output language/locale (default: en-GB):

```fish
# American English
git-commit-message --language en-US "optional context"

# Korean
git-commit-message --language ko-KR

# Japanese
git-commit-message --language ja-JP
```

Notes:

- The model is instructed to write using the selected language/locale.
- In multi-line mode, the only allowed label ("Rationale:") is also translated into the target language.

Environment:

- `OPENAI_API_KEY`: required
- `GIT_COMMIT_MESSAGE_MODEL` or `OPENAI_MODEL`: optional (default: `gpt-5-mini`)
- `GIT_COMMIT_MESSAGE_LANGUAGE` or `OPENAI_LANGUAGE`: optional (default: `en-GB`)

## AI‑generated code notice

Parts of this project were created with assistance from AI tools (e.g. large language models).
All AI‑assisted contributions were reviewed and adapted by maintainers before inclusion.
If you need provenance for specific changes, please refer to the Git history and commit messages.
