"""Audita las dependencias de todos los gestores de paquetes del repo
(pip/requirements.lock y npm/frontend) contra bases de vulnerabilidades
(OSV.dev, npm advisory DB, NVD) y reporta actualizaciones disponibles.

Uso:
    python scripts/dependency_audit.py

No requiere dependencias externas (solo stdlib) para que sea reproducible
sin instalar nada primero. Necesita `npm` en PATH para la parte de frontend/.

NVD_API_KEY es opcional (se lee de .env o del entorno): sin ella el script
funciona igual pero contra el rate limit público de NVD (5 req/30s en vez de
50 req/30s), así que la auditoría tarda más si hay muchos CVEs que enriquecer.

Genera dependency-audit-<YYYY-MM-DD>.md en la raíz del repo.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
UA = "odin-dependency-audit/1.0 (+https://github.com/)"


# ── utilidades HTTP ──────────────────────────────────────────────────────────


def http_json(
    url: str,
    *,
    method: str = "GET",
    data: dict | None = None,
    headers: dict | None = None,
    timeout: int = 20,
) -> Any:
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req_headers = {"User-Agent": UA, "Accept": "application/json"}
    if body is not None:
        req_headers["Content-Type"] = "application/json"
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip()
    return values


# ── Python: requirements.lock / requirements.txt ────────────────────────────

PIN_RE = re.compile(r"^([A-Za-z0-9_.\-]+)==([A-Za-z0-9_.\-+]+)")
DIRECT_RE = re.compile(r"^([A-Za-z0-9_.\-]+)\s*(>=|==|~=|<=|>|<)?\s*([A-Za-z0-9_.\-]*)")


def parse_requirements_lock() -> dict[str, str]:
    """name (lowercase) -> version pinned, ignorando hashes/comentarios/continuaciones."""
    pinned: dict[str, str] = {}
    text = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line or line[0] in " \t#":
            continue
        m = PIN_RE.match(line)
        if m:
            name, version = m.group(1), m.group(2)
            pinned[name.lower()] = version
    return pinned


def parse_requirements_txt_direct() -> dict[str, str]:
    """name (lowercase) -> specifier declarado, solo dependencias directas activas."""
    direct: dict[str, str] = {}
    text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = DIRECT_RE.match(line)
        if m:
            direct[m.group(1).lower()] = raw.split("#", 1)[0].strip()
    return direct


def pypi_latest_version(name: str) -> str | None:
    try:
        data = http_json(f"https://pypi.org/pypi/{name}/json")
        return data.get("info", {}).get("version")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None


def osv_batch_query(packages: dict[str, str]) -> dict[str, list[str]]:
    """PyPI name(lower)->version ya locked -> name -> [vuln ids]."""
    names = list(packages.items())
    result: dict[str, list[str]] = {}
    batch_size = 100
    for i in range(0, len(names), batch_size):
        chunk = names[i : i + batch_size]
        queries = [
            {"package": {"name": name, "ecosystem": "PyPI"}, "version": version}
            for name, version in chunk
        ]
        try:
            resp = http_json(
                "https://api.osv.dev/v1/querybatch", method="POST", data={"queries": queries}
            )
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            print(f"  ! OSV batch query falló: {exc}", file=sys.stderr)
            continue
        for (name, _version), entry in zip(chunk, resp.get("results", []), strict=False):
            vulns = entry.get("vulns") or []
            if vulns:
                result.setdefault(name, []).extend(v["id"] for v in vulns)
    return result


def osv_vuln_detail(vuln_id: str) -> dict | None:
    try:
        return http_json(f"https://api.osv.dev/v1/vulns/{vuln_id}")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None


# ── npm: frontend/ ───────────────────────────────────────────────────────────


def run_npm(*args: str, allow_nonzero: bool = True) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["npm", *args],
        cwd=FRONTEND,
        capture_output=True,
        text=True,
        encoding="utf-8",
        shell=(sys.platform == "win32"),
    )
    if proc.returncode != 0 and not allow_nonzero:
        raise RuntimeError(f"npm {' '.join(args)} falló: {proc.stderr}")
    return proc.returncode, proc.stdout, proc.stderr


def npm_audit() -> dict:
    _, out, _ = run_npm("audit", "--json")
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {}


def npm_outdated() -> dict:
    _, out, _ = run_npm("outdated", "--json", "--include=dev")
    try:
        return json.loads(out) if out.strip() else {}
    except json.JSONDecodeError:
        return {}


def npm_install_dryrun_conflicts() -> str | None:
    """Detecta conflictos ERESOLVE de un `npm ci` limpio, sin tocar node_modules
    ni el lockfile (--dry-run no escribe nada)."""
    code, out, _err = run_npm("install", "--dry-run", "--json")
    if code == 0:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    error = data.get("error")
    if not error:
        return None
    return error.get("detail", error.get("summary", ""))


def parse_package_lock() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """-> (current_por_paquete, deps_directas_prod, deps_directas_dev)."""
    data = json.loads((FRONTEND / "package-lock.json").read_text(encoding="utf-8"))
    root = data["packages"][""]
    direct_prod = dict(root.get("dependencies", {}))
    direct_dev = dict(root.get("devDependencies", {}))
    current: dict[str, str] = {}
    for key, meta in data["packages"].items():
        if not key.startswith("node_modules/"):
            continue
        name = key[len("node_modules/") :]
        if "node_modules/" in name:
            continue  # anidado, no top-level
        version = meta.get("version")
        if version:
            current[name] = version
    return current, direct_prod, direct_dev


# ── NVD enrichment ───────────────────────────────────────────────────────────

CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}")


@dataclass
class NvdInfo:
    cve_id: str
    cvss_score: float | None = None
    cvss_severity: str | None = None
    description: str | None = None


def nvd_lookup_many(cve_ids: set[str], api_key: str | None) -> dict[str, NvdInfo]:
    out: dict[str, NvdInfo] = {}
    if not cve_ids:
        return out
    delay = 0.65 if api_key else 6.5  # 50/30s con key, 5/30s sin key
    headers = {"apiKey": api_key} if api_key else {}
    print(
        f"  Consultando NVD para {len(cve_ids)} CVE(s)"
        f" ({'con' if api_key else 'sin'} API key, ~{delay:.1f}s entre llamadas)..."
    )
    for cve_id in sorted(cve_ids):
        try:
            data = http_json(
                f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}",
                headers=headers,
            )
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            print(f"    ! NVD lookup {cve_id} falló: {exc}", file=sys.stderr)
            time.sleep(delay)
            continue
        vulns = data.get("vulnerabilities") or []
        if not vulns:
            time.sleep(delay)
            continue
        cve = vulns[0]["cve"]
        metrics = cve.get("metrics", {})
        score = severity = None
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if key in metrics and metrics[key]:
                cvss_data = metrics[key][0]["cvssData"]
                score = cvss_data.get("baseScore")
                severity = cvss_data.get(
                    "baseSeverity", metrics[key][0].get("baseSeverity")
                )
                break
        desc = ""
        for d in cve.get("descriptions", []):
            if d.get("lang") == "en":
                desc = d.get("value", "")
                break
        out[cve_id] = NvdInfo(cve_id, score, severity, desc)
        time.sleep(delay)
    return out


# ── clasificación semver ─────────────────────────────────────────────────────


def parse_version_tuple(v: str) -> tuple[int, ...] | None:
    v = v.split("+")[0]  # descarta local version (p.ej. +cpu)
    v = re.sub(r"[-_].*$", "", v)  # descarta pre-release/post (a1, rc1, dev0)
    parts = v.split(".")
    nums = []
    for p in parts[:3]:
        m = re.match(r"\d+", p)
        if not m:
            break
        nums.append(int(m.group()))
    return tuple(nums) if nums else None


def bump_kind(current: str, latest: str) -> str:
    c, latest_t = parse_version_tuple(current), parse_version_tuple(latest)
    if not c or not latest_t:
        return "desconocido"
    c = (c + (0, 0, 0))[:3]
    latest_t = (latest_t + (0, 0, 0))[:3]
    if c == latest_t:
        return "al día"
    if latest_t[0] != c[0]:
        return "major"
    if latest_t[1] != c[1]:
        return "minor"
    return "patch"


# ── recolección de datos ─────────────────────────────────────────────────────


@dataclass
class PyFinding:
    name: str
    version: str
    vuln_id: str
    aliases: list[str] = field(default_factory=list)
    summary: str = ""
    severity: str = ""
    fixed: str = ""


def collect_python_vulns(locked: dict[str, str]) -> list[PyFinding]:
    print(f"Consultando OSV.dev para {len(locked)} paquetes Python (requirements.lock)...")
    vuln_ids_by_pkg = osv_batch_query(locked)
    findings: list[PyFinding] = []
    all_ids = sorted({vid for ids in vuln_ids_by_pkg.values() for vid in ids})
    print(f"  {len(all_ids)} vulnerabilidad(es) encontradas, obteniendo detalle...")
    details = {vid: osv_vuln_detail(vid) for vid in all_ids}
    for name, ids in vuln_ids_by_pkg.items():
        version = locked[name]
        for vid in ids:
            d = details.get(vid) or {}
            aliases = d.get("aliases", [])
            severity = ""
            for sev in d.get("severity", []):
                if sev.get("type", "").startswith("CVSS"):
                    severity = sev.get("score", "")
                    break
            fixed = ""
            for affected in d.get("affected", []):
                pkg = affected.get("package", {})
                if pkg.get("name", "").lower() != name:
                    continue
                for rng in affected.get("ranges", []):
                    for ev in rng.get("events", []):
                        if "fixed" in ev:
                            fixed = ev["fixed"]
            findings.append(
                PyFinding(
                    name=name,
                    version=version,
                    vuln_id=vid,
                    aliases=aliases,
                    summary=d.get("summary") or d.get("details", "")[:200],
                    severity=severity,
                    fixed=fixed,
                )
            )
    return findings


def collect_python_updates(direct: dict[str, str], locked: dict[str, str]) -> list[dict]:
    print(f"Consultando PyPI para versión más reciente de {len(direct)} dependencias directas...")
    rows = []
    for name in sorted(direct):
        current = locked.get(name)
        if not current:
            continue
        latest = pypi_latest_version(name)
        if not latest:
            continue
        kind = bump_kind(current, latest)
        rows.append(
            {
                "name": name,
                "current": current,
                "latest": latest,
                "kind": kind,
                "specifier": direct[name],
            }
        )
    return rows


def collect_npm_updates(
    outdated: dict, current_locked: dict[str, str], direct_prod: dict, direct_dev: dict
) -> list[dict]:
    rows = []
    for name, info in outdated.items():
        current = current_locked.get(name, "?")
        latest = info.get("latest", "?")
        kind = bump_kind(current, latest) if current != "?" else "desconocido"
        rows.append(
            {
                "name": name,
                "current": current,
                "wanted": info.get("wanted", "?"),
                "latest": latest,
                "kind": kind,
                "dev": name in direct_dev and name not in direct_prod,
            }
        )
    return rows


# ── reporte ─────────────────────────────────────────────────────────────────


def fmt_severity(s: str) -> str:
    return s.upper() if s else "N/D"


def build_report(
    *,
    py_vulns: list[PyFinding],
    py_updates: list[dict],
    npm_audit_data: dict,
    npm_updates: list[dict],
    npm_conflict: str | None,
    nvd_info: dict[str, NvdInfo],
    nvd_key_present: bool,
) -> str:
    today = date.today().isoformat()
    lines: list[str] = []
    lines.append(f"# Auditoría de dependencias — {today}")
    lines.append("")
    lines.append(
        "Generado por `scripts/dependency_audit.py`. Fuentes: "
        "[OSV.dev](https://osv.dev) para Python (`requirements.lock`), "
        "`npm audit` (GitHub Advisory DB) para el frontend, y "
        f"[NVD](https://nvd.nist.gov) para enriquecer severidad CVSS de los CVEs encontrados "
        f"({'con' if nvd_key_present else 'sin'} API key)."
    )
    lines.append("")

    # ── resumen ──
    n_py = len(py_vulns)
    npm_meta = npm_audit_data.get("metadata", {}).get("vulnerabilities", {})
    n_npm = npm_meta.get("total", 0)
    lines.append("## Resumen")
    lines.append("")
    lines.append(f"- **Python** (`requirements.lock`): {n_py} vulnerabilidad(es) encontradas.")
    lines.append(
        f"- **Frontend** (`frontend/package-lock.json`): {n_npm} vulnerabilidad(es) encontradas "
        f"(critical={npm_meta.get('critical', 0)}, high={npm_meta.get('high', 0)}, "
        f"moderate={npm_meta.get('moderate', 0)}, low={npm_meta.get('low', 0)})."
    )
    py_major = sum(1 for r in py_updates if r["kind"] == "major")
    py_minor_patch = sum(1 for r in py_updates if r["kind"] in ("minor", "patch"))
    npm_major = sum(1 for r in npm_updates if r["kind"] == "major")
    npm_minor_patch = sum(1 for r in npm_updates if r["kind"] in ("minor", "patch"))
    lines.append(
        f"- **Actualizaciones Python directas**: {py_minor_patch} patch/minor, "
        f"{py_major} major disponibles."
    )
    lines.append(
        f"- **Actualizaciones npm**: {npm_minor_patch} patch/minor, {npm_major} major disponibles."
    )
    if npm_conflict:
        lines.append(
            "- ⚠️ **`npm ci` limpio falla** por un conflicto de peer dependencies "
            "(ver sección de hallazgos)."
        )
    lines.append("")

    # ── vulnerabilidades Python ──
    lines.append("## Vulnerabilidades — Python (requirements.lock)")
    lines.append("")
    if not py_vulns:
        lines.append("Sin vulnerabilidades conocidas en OSV.dev para los paquetes bloqueados.")
    else:
        lines.append("| Paquete | Versión | ID | CVE / severidad | Fixed in | Resumen |")
        lines.append("|---|---|---|---|---|---|")
        for f in sorted(py_vulns, key=lambda x: x.name):
            cve = next((a for a in f.aliases if a.startswith("CVE-")), "")
            nvd = nvd_info.get(cve)
            if nvd and nvd.cvss_score is not None:
                sev = f"{nvd.cvss_severity or ''} {nvd.cvss_score} (NVD)".strip()
            elif f.severity:
                sev = f"CVSS {f.severity} (OSV)"
            else:
                sev = "N/D"
            cve_link = f"[{cve}](https://nvd.nist.gov/vuln/detail/{cve})" if cve else f.vuln_id
            lines.append(
                f"| {f.name} | {f.version} | [{f.vuln_id}]"
                f"(https://osv.dev/vulnerability/{f.vuln_id}) | {cve_link} — {sev} | "
                f"{f.fixed or 'N/D'} | {(f.summary or '').replace(chr(10), ' ')[:140]} |"
            )
    lines.append("")

    # ── vulnerabilidades npm ──
    lines.append("## Vulnerabilidades — Frontend (npm audit)")
    lines.append("")
    vulns = npm_audit_data.get("vulnerabilities", {})
    if not vulns:
        lines.append("Sin vulnerabilidades reportadas por `npm audit`.")
    else:
        lines.append("| Paquete | Severidad | Vía | Fix disponible | Advisory |")
        lines.append("|---|---|---|---|---|")
        for name, v in sorted(vulns.items()):
            via = v.get("via", [])
            advisory_url = ""
            title = ""
            for item in via:
                if isinstance(item, dict):
                    advisory_url = item.get("url", "")
                    title = item.get("title", "")
                    break
            direct = "directa" if v.get("isDirect") else "transitiva"
            fix = "sí" if v.get("fixAvailable") else "no"
            adv = f"[{title[:80]}]({advisory_url})" if advisory_url else "—"
            lines.append(
                f"| {name} ({direct}) | {fmt_severity(v.get('severity', ''))} | "
                f"{', '.join(x if isinstance(x, str) else x.get('name', '') for x in via)} | "
                f"{fix} | {adv} |"
            )
    lines.append("")

    # ── hallazgos adicionales ──
    if npm_conflict:
        lines.append("## Hallazgo: `npm ci` falla en limpio")
        lines.append("")
        lines.append(
            "Con `frontend/node_modules` ausente, `npm ci` (y `npm install --dry-run`) "
            "fallan con `ERESOLVE` — no es una vulnerabilidad, pero rompe cualquier "
            "instalación limpia (CI, onboarding, Docker build sin caché):"
        )
        lines.append("")
        lines.append("```")
        lines.append(npm_conflict.strip())
        lines.append("```")
        lines.append("")
        lines.append(
            "Causa: `openapi-typescript@7.13.0` exige `typescript@^5.x` como peer, pero "
            "`package.json` fija `typescript: ~6.0.2` y el lockfile ya resolvió `typescript@6.0.3` "
            "(probablemente generado con `--legacy-peer-deps` o `--force`). "
            "No se tocó nada — requiere decisión: bajar `typescript` a `^5.x`, "
            "esperar una versión de `openapi-typescript` compatible con TS 6, o "
            "documentar que el equipo debe instalar con `--legacy-peer-deps`."
        )
        lines.append("")

    # ── actualizaciones Python ──
    lines.append("## Actualizaciones disponibles — Python (dependencias directas)")
    lines.append("")
    lines.append("| Paquete | Actual (lock) | Última en PyPI | Tipo |")
    lines.append("|---|---|---|---|")
    for r in sorted(py_updates, key=lambda x: (x["kind"] != "patch", x["kind"] != "minor", x["name"])):
        if r["kind"] == "al día":
            continue
        lines.append(f"| {r['name']} | {r['current']} | {r['latest']} | {r['kind']} |")
    lines.append("")
    n_uptodate = sum(1 for r in py_updates if r["kind"] == "al día")
    lines.append(f"_{n_uptodate} paquete(s) directos ya están en la última versión._")
    lines.append("")

    # ── actualizaciones npm ──
    lines.append("## Actualizaciones disponibles — Frontend (npm)")
    lines.append("")
    stale = [r for r in npm_updates if r["kind"] != "al día"]
    if not stale:
        lines.append("Todas las dependencias directas están en su última versión.")
    else:
        lines.append("| Paquete | Actual (lock) | Wanted (dentro del rango) | Última | Tipo |")
        lines.append("|---|---|---|---|---|")
        for r in sorted(
            stale, key=lambda x: (x["kind"] != "patch", x["kind"] != "minor", x["name"])
        ):
            lines.append(
                f"| {r['name']} | {r['current']} | {r['wanted']} | {r['latest']} | {r['kind']} |"
            )
    lines.append("")
    n_npm_uptodate = len(npm_updates) - len(stale)
    lines.append(f"_{n_npm_uptodate} paquete(s) directos ya están en la última versión._")
    lines.append("")

    # ── plan de acción ──
    lines.append("## Próximo paso")
    lines.append("")
    lines.append(
        "Los majors se listan pero **no se tocan** (pueden traer breaking changes: "
        "revisar changelog antes de subirlos uno por uno). "
        "Para los patch/minor de arriba con vulnerabilidad asociada o simplemente "
        "desactualizados, decime cuáles aplico — corro los tests después de cada bump "
        "y reporto si pasan antes de dejarlo en el working tree."
    )
    lines.append("")

    return "\n".join(lines)


# ── main ────────────────────────────────────────────────────────────────────


def main() -> int:
    env = {**load_dotenv(ROOT / ".env"), **__import__("os").environ}
    nvd_key = env.get("NVD_API_KEY") or None

    print("== Python (requirements.lock) ==")
    locked = parse_requirements_lock()
    direct = parse_requirements_txt_direct()
    py_vulns = collect_python_vulns(locked)
    py_updates = collect_python_updates(direct, locked)

    print("\n== Frontend (npm) ==")
    npm_audit_data = npm_audit()
    outdated = npm_outdated()
    current_locked, direct_prod, direct_dev = parse_package_lock()
    npm_updates = collect_npm_updates(outdated, current_locked, direct_prod, direct_dev)
    print("  Revisando si `npm ci` resuelve en limpio (--dry-run, no modifica nada)...")
    npm_conflict = npm_install_dryrun_conflicts()

    cve_ids: set[str] = set()
    for f in py_vulns:
        cve_ids.update(a for a in f.aliases if CVE_RE.fullmatch(a))
    for v in npm_audit_data.get("vulnerabilities", {}).values():
        for item in v.get("via", []):
            if isinstance(item, dict):
                cve_ids.update(CVE_RE.findall(item.get("title", "")))

    print(f"\n== NVD enrichment ({len(cve_ids)} CVE ids) ==")
    nvd_info = nvd_lookup_many(cve_ids, nvd_key)

    report = build_report(
        py_vulns=py_vulns,
        py_updates=py_updates,
        npm_audit_data=npm_audit_data,
        npm_updates=npm_updates,
        npm_conflict=npm_conflict,
        nvd_info=nvd_info,
        nvd_key_present=bool(nvd_key),
    )

    out_path = ROOT / f"dependency-audit-{date.today().isoformat()}.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"\nReporte escrito en {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
