#!/usr/bin/env /home/apbrandom/.openclaw/tools-venv/bin/python
"""
obsidian skill — file-based vault operations.
Vault: /home/apbrandom/.openclaw/workspace/vault
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
    """search <query>"""
    if not args:
        print("Usage: obsidian search <query>")
        sys.exit(1)

    query = ' '.join(args)
    result = subprocess.run(
        ['grep', '-r', '-l', '-i', query, str(VAULT), '--include=*.md'],
        capture_output=True, text=True
    )

    if not result.stdout.strip():
        print(f"Не найдено: {query}")
        return

    files = result.stdout.strip().split('\n')
    print(f"Найдено в {len(files)} файле(ах) по запросу «{query}»:\n")
    for f in files:
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


def main():
    cmds = {'new': cmd_new, 'search': cmd_search, 'list': cmd_list}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(f"Команды: {', '.join(cmds)}")
        sys.exit(1)
    cmds[sys.argv[1]](sys.argv[2:])


if __name__ == '__main__':
    main()
