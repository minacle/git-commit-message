# git-commit-message

Generate a commit message from your staged changes using OpenAI, Google Gemini, OpenAI-compatible Chat Completions APIs, Ollama, or llama.cpp.

[![asciicast](https://asciinema.org/a/jk0phFqNnc5vaCiIZEYBwZOyN.svg)](https://asciinema.org/a/jk0phFqNnc5vaCiIZEYBwZOyN)

## Requirements

- Python 3.13+
- A Git repo with staged changes (`git add ...`) (or use `--amend` even if nothing is staged)

## Install

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

## Setup

### OpenAI

```sh
export OPENAI_API_KEY="sk-..."
```

### Google Gemini

```sh
export GOOGLE_API_KEY="..."
```

### OpenAI-compatible Chat Completions APIs

Set an API base URL (including `/v1` if required by the server) and a model name:

```sh
export OPENAI_COMPATIBLE_URL="https://api.openai.com/v1"
export OPENAI_COMPATIBLE_MODEL="gpt-5-mini"
export OPENAI_COMPATIBLE_API_KEY="sk-..."
git-commit-message --provider openai-compatible
```

`OPENAI_COMPATIBLE_API_KEY` is optional for servers without authentication.
The provider does not fall back to `OPENAI_API_KEY` or `OPENAI_MODEL`.
The existing `openai` provider continues to use the Responses API.

### Ollama (local models)

1. Install Ollama: https://ollama.ai
2. Start the server:

```sh
ollama serve
```

3. Pull a model:

```sh
ollama pull mistral
```

Optional: set defaults:

```sh
export GIT_COMMIT_MESSAGE_PROVIDER=ollama
export OLLAMA_MODEL=mistral
```

### llama.cpp (local models)

1. Build and run llama.cpp server with your model:

```sh
llama-server -hf ggml-org/gpt-oss-20b-GGUF --host 0.0.0.0 --port 8080
```

2. The server runs on `http://localhost:8080` by default.

Optional: set defaults:

```sh
export GIT_COMMIT_MESSAGE_PROVIDER=llamacpp
export LLAMACPP_URL=http://localhost:8080
```

Note (fish):

```fish
set -x OPENAI_API_KEY "sk-..."
```

## Install (editable)

```sh
python -m pip install -e .
```

## Usage

Generate and print a commit message:

```sh
git add -A
git-commit-message "optional extra context about the change"
```

Generate a single-line subject only (when no trailers are appended):

```sh
git-commit-message --one-line "optional context"

# with trailers, output is subject plus trailer lines
git-commit-message --one-line --co-author 'John Doe <john.doe@example.com>'
```

Use Conventional Commits constraints for the subject/footer only (body format is preserved):

```sh
git-commit-message --conventional

# can be combined with one-line mode
git-commit-message --conventional --one-line

# co-author trailers are appended after any existing footers
git-commit-message --conventional --co-author copilot
```

Select provider:

```sh
# OpenAI (default)
git-commit-message --provider openai

# Google Gemini (via google-genai)
git-commit-message --provider google

# Any compatible Chat Completions server (URL and model are required)
git-commit-message --provider openai-compatible --url http://localhost:8080/v1 --model my-model

# Ollama
git-commit-message --provider ollama

# llama.cpp
git-commit-message --provider llamacpp
```

Commit immediately (optionally open editor):

```sh
git-commit-message --commit "refactor parser for speed"
git-commit-message --commit --edit "refactor parser for speed"

# add co-author trailers
git-commit-message --commit --co-author 'John Doe <john.doe@example.com>'
git-commit-message --commit --co-author 'John Doe <john.doe@example.com>' --co-author 'Jane Doe <jane.doe@example.com>'
git-commit-message --commit --co-author copilot
```

Amend the previous commit:

```sh
# print only (useful for pasting into a GUI editor)
git-commit-message --amend "optional context"

# amend immediately
git-commit-message --commit --amend "optional context"

# amend immediately, but open editor for final tweaks
git-commit-message --commit --amend --edit "optional context"
```

Limit subject length:

```sh
git-commit-message --one-line --max-length 50
```

Chunk/summarise long diffs by token budget:

```sh
# force a single summary pass over the whole diff (default)
git-commit-message --chunk-tokens 0

# chunk the diff into ~4000-token pieces before summarising
git-commit-message --chunk-tokens 4000

# note: for providers 'openai-compatible' and 'ollama', values >= 1 are not supported
# use 0 (single summary pass) or -1 (legacy one-shot)
git-commit-message --provider ollama --chunk-tokens 0

# disable summarisation and use the legacy one-shot prompt
git-commit-message --chunk-tokens -1
```

Adjust unified diff context lines:

```sh
# use 5 context lines around each change hunk
git-commit-message --diff-context 5

# include only changed lines (no surrounding context)
git-commit-message --diff-context 0
```

Select output language/locale (IETF language tag):

```sh
git-commit-message --language en-US
git-commit-message --language ko-KR
git-commit-message --language ja-JP
```

Print debug info:

```sh
git-commit-message --debug
```

Configure Ollama URL (if running on a different machine):

```sh
git-commit-message --provider ollama --url http://192.168.1.100:11434
```

Configure llama.cpp URL:

```sh
git-commit-message --provider llamacpp --url http://192.168.1.100:8080
```

## Options

- `--provider {openai,google,openai-compatible,ollama,llamacpp}`: provider to use (default: `openai`)
- `--model MODEL`: model override (required for `openai-compatible`; provider-specific; ignored for llama.cpp)
- `--language TAG`: output language/locale (default: `en-GB`)
- `--conventional`: apply Conventional Commits constraints to the subject and footer behavior. The body format is unchanged and still includes the translated `Rationale:` line. Breaking changes are expressed with `!` in the subject line, and `BREAKING CHANGE` footer lines are not generated.
- `--one-line`: output subject only when no trailers are appended; with `--co-author`, output is a single-line subject plus `Co-authored-by:` trailer lines
- `--max-length N`: max subject length (default: 72)
- `--chunk-tokens N`: token budget per diff chunk (`0` = single summary pass, `-1` disables summarisation). For `openai-compatible` and `ollama`, values `>= 1` are not supported.
- `--diff-context N`: context lines in unified diff (`N >= 0`). If omitted, uses `GIT_COMMIT_MESSAGE_DIFF_CONTEXT` when set; otherwise uses Git default (usually `3`).
- `--debug`: print request/response details
- `--commit`: run `git commit -m <message>`
- `--amend`: generate a message suitable for amending the previous commit (diff is from the amended commit's parent to the staged index; if nothing is staged, this effectively becomes the diff introduced by `HEAD`)
- `--edit`: with `--commit`, open editor for final message
- `--url URL`: provider URL (default: `http://localhost:11434` for Ollama, `http://localhost:8080` for llama.cpp). For `openai-compatible`, an API base URL is required via this option or `OPENAI_COMPATIBLE_URL`. llama.cpp appends `/v1` to its server URL; `openai-compatible` uses the supplied base URL directly.
- `--host URL`: deprecated alias for `--url`; prints a warning to stderr. Specifying both options is an error.
- `--co-author VALUE`: append `Co-authored-by:` trailer(s). Repeat to add multiple values. Accepted forms: `Name <email@example.com>` or an alias keyword (`claude-code`, `codex`, `copilot`, `copilot-cli`; case-insensitive).

## Environment variables

Required:

- `OPENAI_API_KEY`: when provider is `openai`
- `GOOGLE_API_KEY`: when provider is `google`

Optional:

- `GIT_COMMIT_MESSAGE_PROVIDER`: default provider (`openai` by default). `--provider` overrides this.
- `GIT_COMMIT_MESSAGE_MODEL`: model override for any provider. `--model` overrides this.
- `OPENAI_MODEL`: OpenAI-only model override (used if `--model`/`GIT_COMMIT_MESSAGE_MODEL` are not set)
- `OLLAMA_MODEL`: Ollama-only model override (used if `--model`/`GIT_COMMIT_MESSAGE_MODEL` are not set)
- `OPENAI_COMPATIBLE_URL`: API base URL for `openai-compatible` (required unless `--url` is set)
- `OPENAI_COMPATIBLE_MODEL`: model for `openai-compatible` (required unless `--model` or `GIT_COMMIT_MESSAGE_MODEL` is set)
- `OPENAI_COMPATIBLE_API_KEY`: optional authentication key for `openai-compatible`
- `OLLAMA_URL`: Ollama server URL (default: `http://localhost:11434`)
- `LLAMACPP_URL`: llama.cpp server URL (default: `http://localhost:8080`)
- `OLLAMA_HOST`, `LLAMACPP_HOST`: deprecated fallbacks for the corresponding `*_URL` variables. When set for the selected provider, they print a warning to stderr, including when overridden.
- `GIT_COMMIT_MESSAGE_LANGUAGE`: default language/locale (default: `en-GB`)
- `GIT_COMMIT_MESSAGE_CHUNK_TOKENS`: default chunk token budget (default: `0`; for `openai-compatible` and `ollama`, values `>= 1` are not supported)
- `GIT_COMMIT_MESSAGE_DIFF_CONTEXT`: default unified diff context lines (`0` or greater). If unset, Git default is used (usually `3`).

URL precedence: `--url` (or deprecated `--host`) → provider-specific `*_URL` → deprecated `*_HOST` → provider default. `openai-compatible` has no default URL.

Model precedence for `openai-compatible`: `--model` → `GIT_COMMIT_MESSAGE_MODEL` → `OPENAI_COMPATIBLE_MODEL`. It has no default model.

Default models (if not overridden):

- OpenAI: `gpt-5-mini`
- Google: `gemini-2.5-flash`
- Ollama: `gpt-oss:20b`
- llama.cpp: uses pre-loaded model (model parameter is ignored)

## AI-generated code notice

Parts of this project were created with assistance from AI tools (e.g. large language models).
All AI-assisted contributions were reviewed and adapted by maintainers before inclusion.
If you need provenance for specific changes, please refer to the Git history and commit messages.
