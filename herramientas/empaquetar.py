"""Crea recursos/PasoAPaso.zip con una copia limpia del proyecto.

No incluye bases de datos, sesiones, capturas de pantalla ni carpetas
temporales. El ZIP se puede entregar o descargar desde el portal.
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "recursos" / "PasoAPaso.zip"
TEMPORAL = RAIZ.parent / "_paquete_pasoapaso"

EXCLUIR_CARPETAS = {
    "__pycache__",
    ".git",
    ".venv",
    ".deps",
    ".tmp",
    ".appdata",
    ".tmpdata",
    ".pruebas",
    ".pruebas_tmp",
    "capturas_app",
}
EXCLUIR_ARCHIVOS = {
    ".env",
    "PasoAPaso.zip",
}
EXCLUIR_SUFIJOS = {".pyc", ".pyo", ".db", ".db-wal", ".db-shm"}


def ignorar(directorio: str, nombres: list[str]) -> set[str]:
    ignorados = set()
    directorio_actual = Path(directorio).resolve()
    for nombre in nombres:
        ruta = Path(directorio) / nombre
        # La carpeta «datos» de la raíz es la base de datos de ejecución.
        # La carpeta «pasoapaso/datos» es código del catálogo y sí va en el ZIP.
        if nombre == "datos" and directorio_actual == RAIZ.resolve():
            ignorados.add(nombre)
        elif nombre in EXCLUIR_CARPETAS:
            ignorados.add(nombre)
        elif nombre in EXCLUIR_ARCHIVOS:
            ignorados.add(nombre)
        elif ruta.suffix.lower() in EXCLUIR_SUFIJOS:
            ignorados.add(nombre)
    return ignorados


def main() -> None:
    if TEMPORAL.exists():
        shutil.rmtree(TEMPORAL, ignore_errors=True)
    destino_copia = TEMPORAL / "PasoAPaso"
    shutil.copytree(RAIZ, destino_copia, ignore=ignorar)
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    if DESTINO.exists():
        DESTINO.unlink()
    with zipfile.ZipFile(DESTINO, "w", compression=zipfile.ZIP_DEFLATED) as paquete:
        for ruta in sorted(destino_copia.rglob("*")):
            if ruta.is_dir():
                continue
            relativa = ruta.relative_to(TEMPORAL)
            paquete.write(ruta, arcname=str(relativa))
    shutil.rmtree(TEMPORAL, ignore_errors=True)
    print(f"ZIP creado: {DESTINO}")
    print(f"Tamaño: {DESTINO.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
