# git-commit-message

Staged changes → LLM commit message generator (OpenAI or Google Gemini).

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
# OpenAI
export OPENAI_API_KEY="sk-..."

# Google Gemini
export GOOGLE_API_KEY="AIza..."
```

Note (fish): In fish, set it as follows.

```fish
# OpenAI
set -x OPENAI_API_KEY "sk-..."

# Google Gemini
set -x GOOGLE_API_KEY "AIza..."
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

- Select provider (OpenAI or Google Gemini):

```sh
# Explicit provider
git-commit-message --provider openai "optional context"
git-commit-message --provider google "optional context"

# Provider can be inferred from the model name
git-commit-message --model gemini-2.5-flash "optional context"
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

- API keys (set one depending on provider)
	- `OPENAI_API_KEY`
	- `GOOGLE_API_KEY`
- Model selection (all are optional)
	- Generic: `GIT_COMMIT_MESSAGE_MODEL`
	- OpenAI-specific: `OPENAI_MODEL`
	- Gemini-specific: `GIT_COMMIT_MESSAGE_GEMINI_MODEL` or `GOOGLE_GENAI_MODEL`
- Provider selection (optional)
	- CLI: `--provider openai|google`
	- Env: `GIT_COMMIT_MESSAGE_PROVIDER=openai|google`
	- If omitted, the provider defaults to OpenAI unless the model name contains `gemini`.
- Defaults
	- OpenAI model: `gpt-5-mini`
	- Gemini model: `gemini-2.5-flash`
- Language
	- `GIT_COMMIT_MESSAGE_LANGUAGE` (default: `en-GB`)

## AI‑generated code notice

Parts of this project were created with assistance from AI tools (e.g. large language models).
All AI‑assisted contributions were reviewed and adapted by maintainers before inclusion.
If you need provenance for specific changes, please refer to the Git history and commit messages.
