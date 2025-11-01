# git-commit-message

Staged changes -> GPT commit message generator.

[![asciicast](https://asciinema.org/a/jk0phFqNnc5vaCiIZEYBwZOyN.svg)](https://asciinema.org/a/jk0phFqNnc5vaCiIZEYBwZOyN)

## Install (PyPI)

Install the latest released version from PyPI:

```sh
# User environment (recommended)
python -m pip install --user git-commit-message

# Or system/virtualenv as appropriate
python -m pip install git-commit-message

# Or with pipx for isolated CLI installs
pipx install git-commit-message

# Upgrade to the newest version
python -m pip install --upgrade git-commit-message
```

Quick check:

```sh
git-commit-message --help
```

Set your API key (POSIX sh):

```sh
export OPENAI_API_KEY="sk-..."
```

Note (fish): In fish, set it as follows.

```fish
set -x OPENAI_API_KEY "sk-..."
```

## Install (editable)

```sh
python -m pip install -e .
```

## Usage

- Print commit message only:

```sh
git add -A
git-commit-message "optional extra context about the change"
```

- Force single-line subject only:

```sh
git-commit-message --one-line "optional context"
```

- Limit subject length (default 72):

```sh
git-commit-message --one-line --max-length 50 "optional context"
```

- Commit immediately with editor:

```sh
git-commit-message --commit --edit "refactor parser for speed"
```

- Select output language/locale (default: en-GB):

```sh
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
- `GIT_COMMIT_MESSAGE_LANGUAGE`: optional (default: `en-GB`)

## AI‑generated code notice

Parts of this project were created with assistance from AI tools (e.g. large language models).
All AI‑assisted contributions were reviewed and adapted by maintainers before inclusion.
If you need provenance for specific changes, please refer to the Git history and commit messages.
