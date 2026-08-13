"""Genera el hash de una contraseña para ODIN_AUTH_PASSWORD_HASH.

Uso:
    python scripts/hash_password.py            # pide la clave sin mostrarla
    python scripts/hash_password.py "miclave"  # útil en scripts (queda en el historial del shell)

Pega la línea resultante en tu .env.
"""
from __future__ import annotations

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from odin.core.auth import hash_password  # noqa: E402


def main() -> int:
    if len(sys.argv) > 1:
        plain = sys.argv[1]
    else:
        plain = getpass.getpass("Contraseña: ")
        if plain != getpass.getpass("Repite la contraseña: "):
            print("Las contraseñas no coinciden.", file=sys.stderr)
            return 1

    if len(plain) < 8:
        print("Usa al menos 8 caracteres.", file=sys.stderr)
        return 1

    print()
    print(f"ODIN_AUTH_PASSWORD_HASH={hash_password(plain)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
