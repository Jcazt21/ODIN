"""Un hash almacenado ilegible tiene que distinguirse de una clave equivocada.

Nació de un incidente real: el hash sembrado en `users` traía los separadores
`$` duplicados (`pbkdf2_sha256$$600000$$…`), porque el valor del `.env` llegó
sin que Docker Compose colapsara su escape. `verify_password` no podía
desempaquetarlo en cuatro partes, el `except ValueError` lo convertía en
`False`, y TODA contraseña daba 401 — con el mismo mensaje que una clave
incorrecta. Sin un aviso en el log, la única salida es depurar a mano.
"""
from __future__ import annotations

import logging

from odin.core.auth import hash_password, verify_password


class TestMalformedStoredHash:
    def test_rejects_a_malformed_hash(self):
        assert verify_password("la que sea", "pbkdf2_sha256$$600000$$c2FsdA$$ZGlnZXN0") is False

    def test_warns_so_it_is_not_confused_with_a_wrong_password(self, caplog):
        with caplog.at_level(logging.WARNING):
            verify_password("la que sea", "pbkdf2_sha256$$600000$$c2FsdA$$ZGlnZXN0")

        assert any(
            "hash" in record.message.lower() for record in caplog.records
        ), "un hash ilegible debe avisar en el log, no fallar en silencio"

    def test_a_wrong_password_against_a_valid_hash_stays_silent(self, caplog):
        """El caso normal no debe ensuciar el log: un 401 legítimo es rutina."""
        stored = hash_password("la correcta", iterations=1000)

        with caplog.at_level(logging.WARNING):
            assert verify_password("la incorrecta", stored) is False

        assert caplog.records == []

    def test_a_valid_hash_still_verifies(self):
        stored = hash_password("la correcta", iterations=1000)

        assert verify_password("la correcta", stored) is True
