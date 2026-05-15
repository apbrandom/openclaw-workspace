# obsidian - Obsidian Integration

**Description:** Sync, manage, and query Obsidian vaults with native Markdown support. Supports note creation, query via API, and vault synchronization.

**Commands:**
- `obsidian sync`: Sync local vault with remote (requires `OBSIDIAN_REMOTE` env set)
- `obsidian query <search>`: Search notes via Obsidian API
- `obsidian new <note-name>`: Create new note in default vault

**Configuration:**
- `OBSIDIAN_VAULT`: Path to local vault (default: `~/.obsidian`)
- `OBSIDIAN_REMOTE`: Remote sync URL (e.g., `obsidian://sync?token=xxx`)
- `OBSIDIAN_MODEL`: Model for note generation (default: `qwen3:14b`)