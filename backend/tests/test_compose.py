"""La forma lunga di `env_file` difesa da un test, non solo da un commento.

Nella forma breve (`env_file: .env`) Compose interpreta i `$` dell'hash argon2 di
APP_PASSWORD_HASH come riferimenti a variabili: l'hash arriva al container troncato
— misurato, 62 caratteri su 97 — e da quel momento l'accesso fallisce per qualunque
password, senza un errore da nessuna parte. La forma lunga con `format: raw`
(Compose 2.30 o successivo) è l'unica che lo consegna intero.

Un commento nei file Compose non basta perché il piano di implementazione
(docs/superpowers/plans/2026-09-11-spena-v1.md, righe 123 e 7815) contiene ancora la
forma breve sbagliata: «semplificare» uno dei due file copiandola da lì è un
copia-incolla di distanza, e il sintomo si vede solo provando ad accedere.

docker-compose.e2e.yml non è in questo elenco per un limite dello strumento: usa il
tag `!override` di Compose, che `yaml.safe_load` si rifiuta di costruire. Il suo
`env_file` è comunque in forma lunga, per lo stesso motivo.

PyYAML non è dichiarato tra le dipendenze di questo pacchetto: arriva con
`uvicorn[standard]`, che lo è (verificato nei metadati del pacchetto installato).
"""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILES = ("docker-compose.yml", "docker-compose.prod.yml")

PERCHE = (
    "Serve la forma lunga, non la breve `env_file: .env`:\n"
    "    env_file:\n"
    "      - path: .env\n"
    "        format: raw\n"
    "Senza `format: raw` Compose interpreta i `$` dell'hash argon2 come riferimenti a "
    "variabili e APP_PASSWORD_HASH arriva al container troncato (misurato: 62 caratteri "
    "su 97): l'accesso fallisce per qualunque password e non c'è nessun errore da "
    "leggere. Richiede Compose 2.30 o successivo."
)


@pytest.mark.parametrize("nome_file", COMPOSE_FILES)
def test_il_backend_legge_env_nella_forma_lunga_con_format_raw(nome_file):
    percorso = REPO_ROOT / nome_file
    assert percorso.is_file(), (
        f"{percorso} non esiste: questo test sta cercando nel posto sbagliato, "
        "non è il file Compose a essere a posto"
    )

    backend = yaml.safe_load(percorso.read_text())["services"]["backend"]
    env_file = backend.get("env_file")

    assert isinstance(env_file, list), (
        f"{nome_file}: `env_file` del servizio backend è "
        f"{type(env_file).__name__}, non un elenco. {PERCHE}"
    )

    voci_per_env = [
        voce for voce in env_file if isinstance(voce, dict) and voce.get("path") == ".env"
    ]
    assert voci_per_env, (
        f"{nome_file}: nessuna voce di `env_file` in forma lunga per `.env`; "
        f"trovato {env_file!r}. {PERCHE}"
    )

    for voce in voci_per_env:
        assert voce.get("format") == "raw", (
            f"{nome_file}: la voce di `env_file` per `.env` è {voce!r}, "
            f"senza `format: raw`. {PERCHE}"
        )


@pytest.mark.parametrize("nome_file", COMPOSE_FILES)
def test_il_seme_e_montato_dove_il_comando_di_semina_lo_cerca(nome_file):
    """Il bersaglio del montaggio e i candidati del CLI devono restare d'accordo.

    Sono in due file diversi e nessuno dei due dice dell'altro: se divergono,
    `docker compose exec backend python -m app.cli.seed` muore con FileNotFoundError
    e la v1 non è seminabile dove gira.

    La seconda metà è il motivo per cui il bersaglio è /data: dentro a un altro bind
    mount — in sviluppo /app è ./backend — Docker crea il punto di innesto sul
    filesystem dell'host, e quella cartella nasce di proprietà di root, dentro ai
    sorgenti, non cancellabile senza sudo.
    """
    from app.cli.seed import CANDIDATE_DATA_DIRS

    backend = yaml.safe_load((REPO_ROOT / nome_file).read_text())["services"]["backend"]
    montaggi = [voce.split(":") for voce in backend["volumes"]]
    bersagli = [parti[1] for parti in montaggi if parti[0] == "./data"]

    assert len(bersagli) == 1, (
        f"{nome_file}: mi aspetto un solo montaggio di ./data nel backend, "
        f"trovati {bersagli!r}"
    )
    bersaglio = Path(bersagli[0])
    assert bersaglio in CANDIDATE_DATA_DIRS, (
        f"{nome_file}: ./data è montata su {bersaglio}, che non è tra i candidati di "
        f"app/cli/seed.py ({[str(c) for c in CANDIDATE_DATA_DIRS]}). "
        "Così `python -m app.cli.seed` dentro il container non trova il seme."
    )

    for parti in montaggi:
        if parti[0] == "./data" or not parti[0].startswith("./"):
            continue
        altro_bind = Path(parti[1])
        assert altro_bind not in bersaglio.parents, (
            f"{nome_file}: ./data è montata su {bersaglio}, dentro al bind "
            f"{parti[0]} -> {altro_bind}. Un montaggio annidato fa creare a Docker il "
            f"punto di innesto sull'host, cioè una cartella vuota di proprietà di root "
            f"dentro a {parti[0]} che non si cancella senza sudo."
        )
