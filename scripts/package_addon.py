#!/usr/bin/env python3
"""Validate and package the Horizon Voice Bedrock preview packs."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)
PACKS = {
    "HorizonVoice_BP": ROOT / "addon" / "behavior_pack",
    "HorizonVoice_RP": ROOT / "addon" / "resource_pack",
}


def read_and_validate_manifest(name: str, folder: Path) -> dict:
    manifest_path = folder / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"{name}: manifest.json não encontrado")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{name}: manifest.json inválido: {exc}") from exc

    header_uuid = manifest.get("header", {}).get("uuid")
    try:
        uuid.UUID(str(header_uuid))
    except (ValueError, TypeError, AttributeError) as exc:
        raise SystemExit(f"{name}: header UUID inválido") from exc

    modules = manifest.get("modules")
    if not isinstance(modules, list) or not modules:
        raise SystemExit(f"{name}: modules precisa ser uma lista não vazia")
    uuids = [header_uuid]
    for index, module in enumerate(modules):
        try:
            uuid.UUID(str(module.get("uuid")))
        except (ValueError, TypeError, AttributeError) as exc:
            raise SystemExit(f"{name}: UUID inválido no módulo {index}") from exc
        uuids.append(module["uuid"])
        if module.get("type") == "script":
            entry = module.get("entry")
            if not entry or not (folder / entry).is_file():
                raise SystemExit(f"{name}: script entry ausente: {entry!r}")

    if len(set(uuids)) != len(uuids):
        raise SystemExit(f"{name}: UUID repetido dentro do pack")
    return manifest


def pack_folder(output: Path, folder: Path, archive_prefix: str = "") -> None:
    with ZipFile(output, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for file in sorted(folder.rglob("*")):
            if file.is_file():
                relative = file.relative_to(folder).as_posix()
                archive_name = f"{archive_prefix}{relative}"
                archive.write(file, archive_name)

    with ZipFile(output, "r") as archive:
        bad_file = archive.testzip()
        if bad_file is not None:
            raise SystemExit(f"Arquivo ZIP corrompido em {output.name}: {bad_file}")
        if "manifest.json" not in archive.namelist() and not archive_prefix:
            raise SystemExit(f"{output.name}: manifest.json não está na raiz")


all_uuids: set[str] = set()
for name, folder in PACKS.items():
    manifest = read_and_validate_manifest(name, folder)
    for value in [manifest["header"]["uuid"], *(module["uuid"] for module in manifest["modules"])]:
        if value in all_uuids:
            raise SystemExit(f"UUID reutilizado entre os packs: {value}")
        all_uuids.add(value)
    pack_folder(DIST / f"{name}.mcpack", folder)

addon_path = DIST / "HorizonVoice-BDS-PREVIEW.mcaddon"
with ZipFile(addon_path, "w", ZIP_DEFLATED, compresslevel=9) as archive:
    for name, folder in PACKS.items():
        for file in sorted(folder.rglob("*")):
            if file.is_file():
                archive.write(file, (Path(name) / file.relative_to(folder)).as_posix())

with ZipFile(addon_path, "r") as archive:
    bad_file = archive.testzip()
    required = {"HorizonVoice_BP/manifest.json", "HorizonVoice_RP/manifest.json"}
    if bad_file is not None or not required.issubset(set(archive.namelist())):
        raise SystemExit(f"{addon_path.name}: arquivo inválido ou manifests ausentes")

print("Pacotes BDS de PRÉVIA criados e validados:")
for item in [DIST / "HorizonVoice_BP.mcpack", DIST / "HorizonVoice_RP.mcpack", addon_path]:
    print(f" - {item.relative_to(ROOT)} ({item.stat().st_size} bytes)")
