#!/usr/bin/env python3
"""DbUp.dll içindeki gömülü SQL migration dosyalarını çıkarır."""
from __future__ import annotations

import argparse
import re
import struct
import sys
import zipfile
from io import BytesIO
from pathlib import Path


def _u16(data: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from("<H", data, offset)[0], offset + 2


def _u32(data: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from("<I", data, offset)[0], offset + 4


def parse_pe_resources(dll_path: Path) -> dict[str, bytes]:
    data = dll_path.read_bytes()
    if data[:2] != b"MZ":
        raise ValueError(f"PE dosyası değil: {dll_path}")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_offset : pe_offset + 4] != b"PE\x00\x00":
        raise ValueError("Geçersiz PE imzası")
    coff = pe_offset + 4
    num_sections, section_offset = _u16(data, coff + 2)
    optional_size, _ = _u16(data, coff + 16)
    optional = coff + 20
    magic, _ = _u16(data, optional)
    if magic == 0x10B:
        resource_index_offset = optional + 96 + 2 * 8
    elif magic == 0x20B:
        resource_index_offset = optional + 112 + 2 * 8
    else:
        raise ValueError(f"Desteklenmeyen PE tipi: {magic:#x}")
    resource_rva, _ = _u32(data, resource_index_offset)
    sections: list[dict[str, int]] = []
    off = section_offset
    for _ in range(num_sections):
        virtual_size, off = _u32(data, off + 8)
        virtual_address, off = _u32(data, off)
        raw_size, off = _u32(data, off)
        raw_ptr, off = _u32(data, off)
        sections.append(
            {"va": virtual_address, "vs": virtual_size, "raw": raw_ptr, "size": raw_size}
        )
        off += 16

    def rva_to_offset(rva: int) -> int:
        for section in sections:
            va, vs, raw = section["va"], section["vs"], section["raw"]
            if va <= rva < va + max(vs, section["size"]):
                return raw + (rva - va)
        raise ValueError(f"RVA bulunamadı: {rva}")

    def parse_directory(rva: int) -> dict[str, bytes]:
        offset = rva_to_offset(rva)
        num_named, offset = _u16(data, offset)
        num_id, offset = _u16(data, offset)
        result: dict[str, bytes] = {}
        for _ in range(num_named + num_id):
            name_rva, offset = _u32(data, offset)
            data_rva, offset = _u32(data, offset)
            if name_rva & 0x80000000:
                key = str(name_rva & 0xFFFF)
            else:
                name_off = rva_to_offset(name_rva)
                length, name_off = _u16(data, name_off)
                key = data[name_off : name_off + length * 2].decode("utf-16le", errors="replace")
            if data_rva & 0x80000000:
                child = parse_directory(data_rva & 0x7FFFFFFF)
                for child_key, payload in child.items():
                    full_key = f"{key}.{child_key}" if key else child_key
                    result[full_key] = payload
            else:
                entry_off = rva_to_offset(data_rva)
                data_entry_rva, entry_off = _u32(data, entry_off)
                size, _ = _u32(data, entry_off)
                blob_off = rva_to_offset(data_entry_rva)
                payload = data[blob_off : blob_off + size]
                if len(payload) >= 20 and payload[:4] == b"\x00\x00\x01\x00":
                    inner_size = struct.unpack_from("<I", payload, 16)[0]
                    payload = payload[20 : 20 + inner_size]
                result[key] = payload
        return result

    return parse_directory(resource_rva)


def fallback_binary_extract(data: bytes, output_dir: Path) -> int:
    """PE kaynak okunamazsa ham ikili içinden SQL blokları ayıkla."""
    count = 0
    text = data.decode("latin-1", errors="ignore")
    for match in re.finditer(
        r"(?:--[^\n]*\n)?CREATE\s+(?:TABLE|PROCEDURE|VIEW|INDEX|FUNCTION)\b[\s\S]{80,80000}?",
        text,
        flags=re.IGNORECASE,
    ):
        block = match.group(0).strip()
        if block.count("CREATE") > 20:
            continue
        count += 1
        (output_dir / f"binary_extract_{count:04d}.sql").write_text(block, encoding="utf-8")
    return count


def write_resource(name: str, payload: bytes, output_dir: Path) -> str | None:
    if payload.startswith(b"PK"):
        try:
            with zipfile.ZipFile(BytesIO(payload)) as archive:
                for member in archive.namelist():
                    if member.lower().endswith(".sql"):
                        text = archive.read(member).decode("utf-8", errors="replace")
                        safe = Path(member).name
                        (output_dir / safe).write_text(text, encoding="utf-8")
                        return safe
        except zipfile.BadZipFile:
            pass
    for encoding in ("utf-8", "utf-16le", "latin-1"):
        try:
            text = payload.decode(encoding)
        except UnicodeDecodeError:
            continue
        upper = text.upper()
        if ".SQL" in text or "CREATE TABLE" in upper or "CREATE PROCEDURE" in upper:
            safe = re.sub(r"[^\w.\-]+", "_", name.replace(".", "_")) + ".sql"
            if not safe.endswith(".sql"):
                safe += ".sql"
            (output_dir / safe).write_text(text, encoding="utf-8")
            return safe
    return None


def extract_sql_from_dll(dll_path: Path, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[str] = []
    raw = dll_path.read_bytes()
    try:
        resources = parse_pe_resources(dll_path)
    except Exception:
        resources = {}
    for name, payload in sorted(resources.items()):
        saved = write_resource(name, payload, output_dir)
        if saved:
            manifest.append(saved)
    if not manifest:
        manifest_count = fallback_binary_extract(raw, output_dir)
        manifest = sorted(p.name for p in output_dir.glob("binary_extract_*.sql"))
        if not manifest:
            raise RuntimeError("DLL içinden SQL çıkarılamadı")
        (output_dir / "_manifest.txt").write_text("\n".join(manifest), encoding="utf-8")
        return len(manifest)
    (output_dir / "_manifest.txt").write_text("\n".join(manifest), encoding="utf-8")
    return len(manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description="DbUp SQL çıkarıcı")
    parser.add_argument(
        "--dll",
        type=Path,
        default=Path(
            str(Path.home() / "DbUp.dll")
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "database" / "dbup_extracted",
    )
    args = parser.parse_args()
    if not args.dll.is_file():
        print(f"DLL bulunamadı: {args.dll}", file=sys.stderr)
        return 1
    try:
        count = extract_sql_from_dll(args.dll, args.output)
    except Exception as error:
        print(f"Hata: {error}", file=sys.stderr)
        return 1
    print(f"{count} SQL dosyası çıkarıldı → {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
