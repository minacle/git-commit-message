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

The provider calls llama.cpp's `/chat/completions` and `/tokenize` endpoints
directly with standard-library HTTP requests, without the OpenAI SDK. The chat
endpoint uses the OpenAI-compatible response structure. Verified with llama.cpp
`b11960-8642541b2` (0.8.0); servers must support both endpoints.

1. Install llama.cpp if needed (macOS):

```sh
brew install llama.cpp
```

2. Download/cache a model and run the server. For example, on an Apple Silicon
Mac with 32 GB of memory:

```sh
llama-server \
  --hf-repo Qwen/Qwen3-14B-GGUF:Q4_K_M \
  --alias qwen3-14b \
  --host 127.0.0.1 --port 8080 \
  --gpu-layers all --ctx-size 16384 --parallel 1 \
  --jinja --chat-template-kwargs '{"enable_thinking":false}' \
  --temp 0.7 --top-p 0.8 --top-k 20 --min-p 0
```

The first invocation downloads the GGUF weights; subsequent runs reuse the cache.
Qwen3-14B also has an [MLX release](https://huggingface.co/mlx-community/Qwen3-14B-4bit),
but llama.cpp uses the GGUF weights and does not need MLX installed.

3. Check readiness from another terminal:

```sh
curl --fail http://127.0.0.1:8080/health
```

The expected response after loading is `{"status":"ok"}`. Keep the server running
while using the CLI. The default host is `http://localhost:8080`; supply the server
root URL, without `/v1`.

The server's pre-loaded model is used; `--model` does not select or load a model
for this provider. Chat formatting, thinking, and sampling follow the server's
settings. The client does not set `reasoning_format` or other reasoning options:
it uses only the final assistant `message.content`, leaving any separate reasoning
field out of summaries and commit messages. The server must support the model's
chat template and separate reasoning from final content. Settings that leave
reasoning in `content` (such as `--reasoning-format none` or `--skip-chat-parsing`)
do not meet that requirement. The client does not recognise or strip model-specific
reasoning tags, so it cannot detect reasoning mixed into final content.

The client makes synchronous requests with a 600-second timeout per request and
no automatic retries. It requests `verbose: true` and requires a boolean
`__verbose.truncated` field to verify context preservation. Missing or malformed
metadata and context-truncated responses are rejected, even when `finish_reason`
is `stop`. Empty final answers and other finish reasons (including generation
limits) are also rejected.

Positive `--chunk-tokens` values count raw diff tokens through `/tokenize`,
excluding special tokens and chat-template overhead. Leave room for instructions,
context, and output: this budget does not guarantee the full request fits the
server's context window. `0` uses one summary pass; `-1` skips summarisation.

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

# note: for provider 'ollama', values >= 1 are not supported
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
- `--conventional`: apply Conventional Commits constraints to the subject and footer behavior. The body format is unchanged and still includes the translated `Rationale:` line. Breaking changes are expressed with `!` in the subject line, and `BREAKING CHANGE` footer lines are not generated.
- `--one-line`: output subject only when no trailers are appended; with `--co-author`, output is a single-line subject plus `Co-authored-by:` trailer lines
- `--max-length N`: max subject length (default: 72)
- `--chunk-tokens N`: token budget per diff chunk (`0` = single summary pass, `-1` disables summarisation). For `ollama`, values `>= 1` are not supported.
- `--diff-context N`: context lines in unified diff (`N >= 0`). If omitted, uses `GIT_COMMIT_MESSAGE_DIFF_CONTEXT` when set; otherwise uses Git default (usually `3`).
- `--debug`: print request/response details
- `--commit`: run `git commit -m <message>`
- `--amend`: generate a message suitable for amending the previous commit (diff is from the amended commit's parent to the staged index; if nothing is staged, this effectively becomes the diff introduced by `HEAD`)
- `--edit`: with `--commit`, open editor for final message
- `--host URL`: host URL for providers like Ollama or llama.cpp (default: `http://localhost:11434` for Ollama, `http://localhost:8080` for llama.cpp)
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
- `OLLAMA_HOST`: Ollama server URL (default: `http://localhost:11434`)
- `LLAMACPP_HOST`: llama.cpp server URL (default: `http://localhost:8080`)
- `LLAMACPP_MODEL`: llama.cpp-only model label override; the server's pre-loaded model is still used
- `GIT_COMMIT_MESSAGE_LANGUAGE`: default language/locale (default: `en-GB`)
- `GIT_COMMIT_MESSAGE_CHUNK_TOKENS`: default chunk token budget (default: `0`; for `ollama`, values `>= 1` are not supported)
- `GIT_COMMIT_MESSAGE_DIFF_CONTEXT`: default unified diff context lines (`0` or greater). If unset, Git default is used (usually `3`).

Default models (if not overridden):

- OpenAI: `gpt-5-mini`
- Google: `gemini-2.5-flash`
- Ollama: `gpt-oss:20b`
- llama.cpp: uses pre-loaded model (model parameter is ignored)

## AI-generated code notice

Parts of this project were created with assistance from AI tools (e.g. large language models).
All AI-assisted contributions were reviewed and adapted by maintainers before inclusion.
If you need provenance for specific changes, please refer to the Git history and commit messages.
