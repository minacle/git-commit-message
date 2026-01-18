# git-commit-message

Generate a commit message from your staged changes using OpenAI, Google Gemini, Ollama, or llama.cpp.

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
export LLAMACPP_HOST=http://localhost:8080
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

Generate a single-line subject only:

```sh
git-commit-message --one-line "optional context"
```

Select provider:

```sh
# OpenAI (default)
git-commit-message --provider openai

# Google Gemini (via google-genai)
git-commit-message --provider google

# Ollama
git-commit-message --provider ollama

# llama.cpp
git-commit-message --provider llamacpp
```

Commit immediately (optionally open editor):

```sh
git-commit-message --commit "refactor parser for speed"
git-commit-message --commit --edit "refactor parser for speed"
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

# disable summarisation and use the legacy one-shot prompt
git-commit-message --chunk-tokens -1
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

Configure Ollama host (if running on a different machine):

```sh
git-commit-message --provider ollama --host http://192.168.1.100:11434
```

Configure llama.cpp host:

```sh
git-commit-message --provider llamacpp --host http://192.168.1.100:8080
```

## Options

- `--provider {openai,google,ollama,llamacpp}`: provider to use (default: `openai`)
- `--model MODEL`: model override (provider-specific; ignored for llama.cpp)
- `--language TAG`: output language/locale (default: `en-GB`)
- `--one-line`: output subject only
- `--max-length N`: max subject length (default: 72)
- `--chunk-tokens N`: token budget per diff chunk (`0` = single summary pass, `-1` disables summarisation)
- `--debug`: print request/response details
- `--commit`: run `git commit -m <message>`
- `--amend`: generate a message suitable for amending the previous commit (diff is from the amended commit's parent to the staged index; if nothing is staged, this effectively becomes the diff introduced by `HEAD`)
- `--edit`: with `--commit`, open editor for final message
- `--host URL`: host URL for providers like Ollama or llama.cpp (default: `http://localhost:11434` for Ollama, `http://localhost:8080` for llama.cpp)

## Environment variables

Required:

- `OPENAI_API_KEY`: when provider is `openai`
- `GOOGLE_API_KEY`: when provider is `google`

Optional:

- `GIT_COMMIT_MESSAGE_PROVIDER`: default provider (`openai` by default). `--provider` overrides this.
- `GIT_COMMIT_MESSAGE_MODEL`: model override for any provider. `--model` overrides this.
- `OPENAI_MODEL`: OpenAI-only model override (used if `--model`/`GIT_COMMIT_MESSAGE_MODEL` are not set)
- `OLLAMA_MODEL`: Ollama-only model override (used if `--model`/`GIT_COMMIT_MESSAGE_MODEL` are not set)
- `OLLAMA_HOST`: Ollama server URL (default: `http://localhost:11434`)
- `LLAMACPP_HOST`: llama.cpp server URL (default: `http://localhost:8080`)
- `GIT_COMMIT_MESSAGE_LANGUAGE`: default language/locale (default: `en-GB`)
- `GIT_COMMIT_MESSAGE_CHUNK_TOKENS`: default chunk token budget (default: `0`)

Default models (if not overridden):

- OpenAI: `gpt-5-mini`
- Google: `gemini-2.5-flash`
- Ollama: `gpt-oss:20b`
- llama.cpp: uses pre-loaded model (model parameter is ignored)

## AI-generated code notice

Parts of this project were created with assistance from AI tools (e.g. large language models).
All AI-assisted contributions were reviewed and adapted by maintainers before inclusion.
If you need provenance for specific changes, please refer to the Git history and commit messages.
