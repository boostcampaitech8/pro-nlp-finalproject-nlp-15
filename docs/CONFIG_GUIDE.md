# Configuration Guide

This project uses [Hydra](https://hydra.cc/) to manage complex, modular configurations. This guide explains the structure, key settings, and how to customize the system.

## Structure Overview

All configurations reside in the `config/` directory, organized into logical groups:

- **`config/app/`**: Application-specific settings like asset definitions and prompts.
- **`config/infra/`**: Infrastructure settings including data paths, database connections, and RAG/Vector DB settings.
- **`config/llm/`**: LLM provider configurations (e.g., Gemini, OpenAI).
- **`config/*.yaml`**: Entry-level configurations for specific workflows (e.g., `ingest_raw.yaml`).

## Key Configuration Files

### 1. Data Paths (`config/infra/data.yaml`)
Manages all external data locations.
- **`prices_dir`**: Directory for price CSV files.
- **`articles_dir`**: Directory for article CSV files.
- **`events_dir`**: Directory for event JSONL files.
- **`chunks_dir`**: Destination for processed text chunks.
- **`db_path`**: Path to the SQLite database (typically `sqlite/stockinfo.db`).
- **`manifest_path`**: Path to the resource manifest.

> [!NOTE]
> Paths in this file are relative to the project root. The system automatically resolves them to absolute paths using a `resolve_path` utility in the workflow scripts.

### 2. Database (`config/infra/database.yaml`)
Configures the primary data store.
- **`type`**: `sqlite` or `mysql`.
- **`mysql`**: Connection details for production MySQL environments.
- **`sqlite`**: Settings like `journal_mode: WAL` and `synchronous: NORMAL` for local performance.

### 3. RAG and Vector DB (`config/infra/rag.yaml`)
Settings for semantic search and Qdrant.
- **`vector_db`**: Qdrant URL and collection names (`knowledge_base_collection`, `event_collection`).
- **`embedding`**: Defines the dense and sparse models used for vectorization.

### 4. Assets (`config/app/assets.yaml`)
Defines the commodities and symbols tracked by the system.
```yaml
assets:
  - symbol: "GOLD"
    name: "Gold Futures"
    keywords: ["gold", "xau"]
```

## How to Customize

### Command Line Overrides
You can override any configuration value directly from the CLI when running a script:
```bash
# Change the database type to mysql for a single run
uv run python workflow/run_ingest_raw.py database.type=mysql

# Rebuild the database
uv run python workflow/run_ingest_raw.py rebuild=true
```

### Switching Environments
The root config files (e.g., `chatbot.yaml`) use `defaults` to compose the final configuration:
```yaml
defaults:
  - /infra@database: database # Uses config/infra/database.yaml
  - /llm: gemini             # Uses config/llm/gemini.yaml
```
To switch from Gemini to local LLM, you can change the default or override via CLI: `llm=local`.
