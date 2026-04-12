#!/usr/bin/env python3
"""
PO to MO compiler for SkyCLI i18n using Babel
"""
from pathlib import Path
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po


def compile_po_to_mo(po_path: str, mo_path: str):
    """Compile a .po file to .mo format using Babel"""
    with open(po_path, 'rb') as f:
        catalog = read_po(f)

    with open(mo_path, 'wb') as f:
        write_mo(f, catalog)

    print(f"Compiled: {po_path} -> {mo_path}")


def main():
    base_dir = Path(__file__).parent.parent
    locale_dir = base_dir / "locale"

    for lang_dir in sorted(locale_dir.iterdir()):
        if lang_dir.is_dir() and lang_dir.name != '__pycache__':
            po_file = lang_dir / "LC_MESSAGES" / "messages.po"
            mo_file = lang_dir / "LC_MESSAGES" / "messages.mo"

            if po_file.exists():
                compile_po_to_mo(str(po_file), str(mo_file))


if __name__ == "__main__":
    main()
