"""Carica la tabella CIQUAL 2025 dell'Anses in `ciqual_foods` (S4, fetta 1).

    python -m app.cli.load_ciqual --dry-run        # legge, conta, stampa; non scrive
    python -m app.cli.load_ciqual                  # data/ciqual/ciqual-2025.xlsx
    python -m app.cli.load_ciqual <percorso.xlsx>  # un altro file

Il file è l'XLSX della scheda ufficiale (https://doi.org/10.57745/RDMHWY), messo nel
repository da Mattia: `data/` è montata su `/data` nei container (spec §4.1). La prova a
secco non apre nemmeno il database: si può lanciare ovunque, prima di tutto. Il
caricamento vero aggiorna per codice e non cancella niente; un file che non torna
(un'unità diversa, una colonna d'obbligo che manca) non scrive niente e dice perché.
"""

import asyncio
import sys
from pathlib import Path

from app.core.config import REPO_ROOT
from app.core.db import SessionLocal
from app.domain.ciqual import CIQUAL_NAMES, CIQUAL_URL, CIQUAL_VERSION, CiqualFormatError
from app.domain.nutrients import NUTRIENT_FIELDS
from app.repositories.ciqual import count_missing_from, upsert_foods
from app.services.ciqual_file import CiqualFile, read_ciqual

FLAG_DRY_RUN = "--dry-run"
DEFAULT_FILE = Path("ciqual") / "ciqual-2025.xlsx"
# fuori dal container il file sta nel repository; dentro, `data/` è montata su /data
CANDIDATE_FILES: tuple[Path, ...] = (REPO_ROOT / "data" / DEFAULT_FILE, Path("/data") / DEFAULT_FILE)

HOWTO_MISSING = (
    f"Non trovo la tabella CIQUAL (data/{DEFAULT_FILE.as_posix()}). Scaricala da {CIQUAL_URL} "
    "— il file «Table Ciqual 2025_FR_2025_11_03.xlsx» — e mettila in "
    f"data/{DEFAULT_FILE.as_posix()}, oppure passa il percorso del file."
)


def _default_file() -> Path | None:
    for candidate in CANDIDATE_FILES:
        if candidate.is_file():
            return candidate
    return None


def report_lines(file: CiqualFile, name: str) -> list[str]:
    lines = [f"{name}: {len(file.foods)} alimenti letti.", "Valori per nutriente:"]
    for key in CIQUAL_NAMES:
        if key in file.absent:
            continue
        field = NUTRIENT_FIELDS[key]
        line = f"  {field.label} ({field.unit}): {file.with_value.get(key, 0)} alimenti"
        bad = file.unreadable.get(key, 0)
        if bad:
            line += f", {bad} " + ("illeggibile" if bad == 1 else "illeggibili")
        lines.append(line)
    if file.absent:
        labels = ", ".join(NUTRIENT_FIELDS[key].label for key in file.absent)
        lines.append(f"Nel vocabolario ma non nel file: {labels}.")
    if file.unused:
        lines.append(f"Colonne non usate: {len(file.unused)}, per esempio «{file.unused[0]}».")
    if file.skipped_rows:
        lines.append(f"Righe senza codice o senza nome, saltate: {file.skipped_rows}.")
    if file.duplicate_codes:
        lines.append(f"Righe con un codice già letto, saltate: {file.duplicate_codes}.")
    return lines


async def main(argv: list[str]) -> int:
    dry_run = FLAG_DRY_RUN in argv
    rest = [arg for arg in argv if arg != FLAG_DRY_RUN]
    # La guardia esce con codice diverso da zero, non solo stampando: un refuso in uno
    # script che controlla l'exit code non deve passare per un successo.
    flags = [arg for arg in rest if arg.startswith("--")]
    if flags:
        print(f"argomento sconosciuto: {flags[0]}")
        return 2
    if len(rest) > 1:
        print(f"uso: python -m app.cli.load_ciqual [{FLAG_DRY_RUN}] [percorso.xlsx]")
        return 2
    if rest:
        path = Path(rest[0])
        if not path.is_file():
            print(f"Non trovo il file «{path}».")
            return 1
    else:
        found = _default_file()
        if found is None:
            print(HOWTO_MISSING)
            return 1
        path = found

    try:
        file = read_ciqual(path)
    except CiqualFormatError as exc:
        print(f"Il file non va: {exc}. Niente è stato scritto.")
        return 1
    for line in report_lines(file, path.name):
        print(line)
    if dry_run:
        print("Prova a secco: niente è stato scritto.")
        return 0

    async with SessionLocal() as session:
        written = await upsert_foods(session, file.foods)
        missing = await count_missing_from(session, {food.code for food in file.foods})
        await session.commit()
    print(f"{written} alimenti scritti in CIQUAL {CIQUAL_VERSION}.")
    if missing == 1:
        print("1 alimento già nel database non è nel file: resta com'è.")
    elif missing:
        print(f"{missing} alimenti già nel database non sono nel file: restano come sono.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
