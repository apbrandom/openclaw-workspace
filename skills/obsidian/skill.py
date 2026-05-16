#!/usr/bin/env /home/apbrandom/.openclaw/tools-venv/bin/python
"""
obsidian skill — file-based vault operations.
Vault: /home/apbrandom/.openclaw/workspace/vault
Commands: new, search, list, move, delete, open
"""
import sys
import re
import subprocess
from pathlib import Path
from datetime import datetime

VAULT = Path("/home/apbrandom/.openclaw/workspace/vault")
SHIPS_DIR = VAULT / "ships"


def slugify(name: str) -> str:
    return re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')


def resolve(name: str) -> Path:
    """Resolve note name or path relative to vault."""
    p = Path(name)
    if p.suffix == '.md':
        return VAULT / p if not p.is_absolute() else p
    return VAULT / (str(p) + '.md')


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_new(args):
    """new <name> [--folder <folder>] [--ship <SHIP>]"""
    if not args:
        print("Usage: obsidian new <name> [--folder <folder>] [--ship <SHIP>]")
        sys.exit(1)

    name = args[0]
    folder = None
    ship = None
    i = 1
    while i < len(args):
        if args[i] == '--folder' and i + 1 < len(args):
            folder = args[i + 1]; i += 2
        elif args[i] == '--ship' and i + 1 < len(args):
            ship = args[i + 1].upper().replace(' ', '_'); i += 2
        else:
            i += 1

    target_dir = VAULT / folder if folder else VAULT
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / (slugify(name) + '.md')

    if target.exists():
        print(f"Already exists: {target.relative_to(VAULT)}")
        sys.exit(1)

    today = datetime.now().strftime('%Y-%m-%d')
    lines = ['---', f'date: {today}', f'title: "{name}"']
    if ship:
        lines.append(f'ship: {ship}')
    lines += ['---', '', f'# {name}', '']

    if ship:
        ship_file = SHIPS_DIR / f'{ship}.md'
        if ship_file.exists():
            lines.append(f'Судно: [[ships/{ship}]]')
        else:
            lines.append(f'Судно: {ship} (карточка не найдена в vault/ships/)')
        lines.append('')

    target.write_text('\n'.join(lines), encoding='utf-8')
    print(f"Created: {target.relative_to(VAULT)}")


def cmd_search(args):
    """search <query> [--folder <folder>]"""
    if not args:
        print("Usage: obsidian search <query> [--folder <folder>]")
        sys.exit(1)

    folder = None
    query_parts = []
    i = 0
    while i < len(args):
        if args[i] == '--folder' and i + 1 < len(args):
            folder = args[i + 1]; i += 2
        else:
            query_parts.append(args[i]); i += 1

    query = ' '.join(query_parts)
    search_root = VAULT / folder if folder else VAULT

    result = subprocess.run(
        ['grep', '-r', '-l', '-i', query, str(search_root), '--include=*.md'],
        capture_output=True, text=True
    )

    if not result.stdout.strip():
        print(f"Не найдено: {query}")
        return

    files = result.stdout.strip().split('\n')
    print(f"Найдено в {len(files)} файле(ах) по запросу «{query}»:\n")
    for f in files:
        if '.obsidian' in f:
            continue
        rel = Path(f).relative_to(VAULT)
        lines_out = subprocess.run(
            ['grep', '-n', '-i', query, f],
            capture_output=True, text=True
        ).stdout.strip().split('\n')
        print(f"  {rel}")
        for line in lines_out[:3]:
            print(f"    {line}")
        print()


def cmd_list(args):
    """list [folder]"""
    folder = args[0] if args else None
    target = VAULT / folder if folder else VAULT
    if not target.exists():
        print(f"Папка не найдена: {folder}")
        sys.exit(1)

    notes = sorted(p for p in target.rglob('*.md') if '.obsidian' not in p.parts)
    if not notes:
        print("Нет заметок.")
        return
    for note in notes:
        print(note.relative_to(VAULT))


def cmd_move(args):
    """move <old-path> <new-path>  — moves note and updates [[wikilinks]]"""
    if len(args) < 2:
        print("Usage: obsidian move <old> <new>")
        sys.exit(1)

    src = resolve(args[0])
    dst = resolve(args[1])

    if not src.exists():
        print(f"Не найдено: {src.relative_to(VAULT)}")
        sys.exit(1)
    if dst.exists():
        print(f"Уже существует: {dst.relative_to(VAULT)}")
        sys.exit(1)

    dst.parent.mkdir(parents=True, exist_ok=True)

    # Update wikilinks in all vault notes before moving
    old_stem = src.stem
    new_stem = dst.stem
    old_folder = src.parent.relative_to(VAULT)
    new_folder = dst.parent.relative_to(VAULT)

    updated = []
    for note in VAULT.rglob('*.md'):
        if '.obsidian' in note.parts:
            continue
        content = note.read_text(encoding='utf-8')
        new_content = content
        # Replace [[old_stem]] and [[folder/old_stem]]
        new_content = re.sub(
            rf'\[\[{re.escape(str(old_folder / old_stem))}\]\]',
            f'[[{new_folder / new_stem}]]',
            new_content
        )
        new_content = re.sub(
            rf'\[\[{re.escape(old_stem)}\]\]',
            f'[[{new_stem}]]',
            new_content
        )
        if new_content != content:
            note.write_text(new_content, encoding='utf-8')
            updated.append(note.relative_to(VAULT))

    src.rename(dst)
    print(f"Moved: {src.relative_to(VAULT)} → {dst.relative_to(VAULT)}")
    if updated:
        print(f"Wikilinks обновлены в {len(updated)} файлах:")
        for u in updated:
            print(f"  {u}")


def cmd_delete(args):
    """delete <note-path>"""
    if not args:
        print("Usage: obsidian delete <note-path>")
        sys.exit(1)

    target = resolve(args[0])
    if not target.exists():
        print(f"Не найдено: {args[0]}")
        sys.exit(1)

    # Use trash if available, otherwise warn
    trash = subprocess.run(['which', 'trash'], capture_output=True).returncode == 0
    if trash:
        subprocess.run(['trash', str(target)])
        print(f"В корзину: {target.relative_to(VAULT)}")
    else:
        target.unlink()
        print(f"Удалено: {target.relative_to(VAULT)}")


def cmd_open(args):
    """open <note-path>  — open in Windows Obsidian via URI (WSL2)"""
    if not args:
        print("Usage: obsidian open <note-path>")
        sys.exit(1)

    target = resolve(args[0])
    if not target.exists():
        print(f"Не найдено: {args[0]}")
        sys.exit(1)

    # Determine vault name (folder name)
    vault_name = VAULT.name
    rel = target.relative_to(VAULT)
    note_path = str(rel).replace('\\', '/').removesuffix('.md')

    uri = f"obsidian://open?vault={vault_name}&file={note_path}"
    result = subprocess.run(
        ['powershell.exe', '-Command', f'Start-Process "{uri}"'],
        capture_output=True
    )
    if result.returncode == 0:
        print(f"Открыто в Obsidian: {note_path}")
    else:
        print(f"Не удалось открыть. URI: {uri}")


def main():
    cmds = {
        'new': cmd_new,
        'search': cmd_search,
        'list': cmd_list,
        'move': cmd_move,
        'delete': cmd_delete,
        'open': cmd_open,
    }
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(f"Команды: {', '.join(cmds)}")
        sys.exit(1)
    cmds[sys.argv[1]](sys.argv[2:])


if __name__ == '__main__':
    main()
