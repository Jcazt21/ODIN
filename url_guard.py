"""Descarga controlada de URLs suministradas por el usuario (anti-SSRF).

`POST /api/analyze` recibe una URL arbitraria y devuelve al llamante lo que el
servidor descargó: sin control, el backend es un proxy de lectura hacia todo lo
que él alcanza y el usuario no (metadata de la nube en 169.254.169.254, `db:5432`,
cualquier host de la red interna).

Tres capas, en orden de fuerza:

1. **Allowlist de dominios** — el producto solo analiza medios dominicanos. Es
   una defensa mucho más fuerte que una denylist de IPs, porque no depende de
   haber enumerado bien todos los rangos peligrosos.
2. **Bloqueo de IPs no públicas** — se resuelve el hostname *antes* de conectar y
   se rechaza loopback, privadas, link-local (169.254/16), CGNAT, multicast y
   reservadas. Se revalida en **cada salto de redirección**.
3. **Límites de la respuesta** — tamaño máximo y `Content-Type` permitido.

Nota sobre DNS rebinding: entre la resolución y la conexión hay una ventana en la
que el DNS podría cambiar. Cerrarla del todo exige conectar por IP y forzar el
Host/SNI a mano. No lo hacemos porque la capa 1 ya obliga al atacante a controlar
el DNS de un dominio de la allowlist, y en ese escenario el rebinding es el menor
de los problemas.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urljoin, urlsplit

import requests

from config import settings

log = logging.getLogger("odin.url_guard")


class UrlNotAllowed(Exception):
    """La URL no pasa la validación. El mensaje va tal cual al usuario."""


# CGNAT (RFC 6598). `is_private` ya lo cubre en Python moderno; lo dejamos
# explícito para no depender de esa versión.
_CGNAT = ipaddress.ip_network("100.64.0.0/10")

_ALLOWED_SCHEMES = ("http", "https")
_ALLOWED_PORTS = (None, 80, 443)

# El cuerpo de un artículo es texto. Nada de imágenes, PDFs ni binarios.
_ALLOWED_CONTENT_TYPES = (
    "text/html",
    "application/xhtml+xml",
    "text/plain",
    "text/xml",
    "application/xml",
    "application/rss+xml",
)


def _ip_is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # ::ffff:169.254.169.254 es la metadata de la nube disfrazada de IPv6.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if isinstance(ip, ipaddress.IPv4Address) and ip in _CGNAT:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _host_allowed(host: str) -> bool:
    """True si el host es un dominio de la allowlist o un subdominio suyo."""
    host = host.lower().rstrip(".")
    return any(
        host == domain or host.endswith(f".{domain}")
        for domain in settings.allowed_domains
    )


def validate_url(url: str) -> str:
    """Valida esquema, puerto, dominio y destino IP. Devuelve la URL normalizada
    o lanza UrlNotAllowed."""
    url = url.strip()

    if len(url) > settings.max_url_length:
        raise UrlNotAllowed("La URL es demasiado larga.")

    try:
        parts = urlsplit(url)
    except ValueError:
        raise UrlNotAllowed("URL inválida.") from None

    if parts.scheme not in _ALLOWED_SCHEMES:
        raise UrlNotAllowed("Solo se aceptan URLs http:// o https://.")

    # `http://listindiario.com@evil.com/` apunta a evil.com aunque parezca lo
    # contrario. No hay razón legítima para credenciales en la URL de un diario.
    if parts.username or parts.password:
        raise UrlNotAllowed("La URL no puede llevar credenciales.")

    host = parts.hostname
    if not host:
        raise UrlNotAllowed("URL inválida: falta el dominio.")

    try:
        port = parts.port
    except ValueError:
        raise UrlNotAllowed("Puerto inválido.") from None
    if port not in _ALLOWED_PORTS:
        raise UrlNotAllowed("Solo se aceptan los puertos 80 y 443.")

    if not _host_allowed(host):
        raise UrlNotAllowed(
            f"El dominio '{host}' no está permitido. Odin solo analiza los medios "
            "configurados en ODIN_ALLOWED_DOMAINS."
        )

    _assert_resolves_to_public_ip(host)
    return url


def _assert_resolves_to_public_ip(host: str) -> None:
    """Resuelve el hostname y exige que **todas** sus IPs sean públicas.

    Todas, no alguna: si un nombre devuelve una IP pública y una interna, seguir
    adelante dejaría que el sistema operativo eligiera la interna."""
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise UrlNotAllowed(f"No se pudo resolver el dominio '{host}'.") from None

    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise UrlNotAllowed(f"No se pudo resolver el dominio '{host}'.")

    for raw in addresses:
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError:
            raise UrlNotAllowed(f"Dirección inválida para '{host}'.") from None
        if not _ip_is_public(ip):
            log.warning("bloqueado destino no público: %s -> %s", host, raw)
            raise UrlNotAllowed(
                f"El dominio '{host}' apunta a una dirección interna."
            )


def _content_type_allowed(header: str | None) -> bool:
    if not header:
        return False
    mime = header.split(";", 1)[0].strip().lower()
    return mime in _ALLOWED_CONTENT_TYPES


def _read_capped(resp: requests.Response, max_bytes: int) -> str:
    """Lee el cuerpo cortando en max_bytes, sin cargar de más en memoria."""
    declared = resp.headers.get("Content-Length")
    if declared and declared.isdigit() and int(declared) > max_bytes:
        raise UrlNotAllowed("La página es demasiado grande.")

    chunks: list[bytes] = []
    total = 0
    for chunk in resp.iter_content(8192):
        total += len(chunk)
        if total > max_bytes:
            raise UrlNotAllowed("La página es demasiado grande.")
        chunks.append(chunk)

    return b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")


def fetch_html(url: str, *, session: requests.Session | None = None) -> str:
    """Descarga una URL de usuario con todas las protecciones puestas.

    Las redirecciones se siguen a mano (`allow_redirects=False`) para poder
    revalidar cada destino: un redirect 302 hacia 169.254.169.254 se salta
    cualquier validación que solo mire la URL original.
    """
    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", settings.user_agent)

    current = validate_url(url)

    for _ in range(settings.max_redirects + 1):
        resp = sess.get(
            current,
            timeout=settings.fetch_timeout,
            allow_redirects=False,
            stream=True,
        )
        try:
            if resp.is_redirect or resp.is_permanent_redirect:
                location = resp.headers.get("Location")
                if not location:
                    raise UrlNotAllowed("Redirección sin destino.")
                # Location puede ser relativa; urljoin la resuelve contra la actual.
                current = validate_url(urljoin(current, location))
                continue

            if resp.status_code >= 400:
                raise UrlNotAllowed(
                    f"El sitio respondió {resp.status_code} al pedir la página."
                )

            if not _content_type_allowed(resp.headers.get("Content-Type")):
                raise UrlNotAllowed("La URL no devuelve una página HTML.")

            return _read_capped(resp, settings.max_download_bytes)
        finally:
            resp.close()

    raise UrlNotAllowed("Demasiadas redirecciones.")
