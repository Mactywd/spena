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
ENTRYPOINT = REPO_ROOT / "backend" / "docker-entrypoint.sh"
DOCKERFILE = REPO_ROOT / "backend" / "Dockerfile"

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


def test_le_migrazioni_girano_allavvio_del_backend():
    """Spec §13: «Le migrazioni Alembic girano all'avvio del backend».

    Prima no: il Dockerfile lanciava uvicorn e nient'altro, e il passo stava solo nel
    README. Il costo era zero finché l'ultima migrazione era la 0003 e arrivava tutto
    insieme alla prima successiva — `git pull`, `up -d --build`, e il backend serve
    contro uno schema vecchio con ogni chiamata a 500.

    Sono tre pezzi che devono restare d'accordo fra tre file diversi, e nessuno dei
    tre dice degli altri: l'entrypoint che migra, il Dockerfile che lo invoca, e il
    `set -e` che fa morire il container invece di servire contro lo schema sbagliato.
    """
    # solo le istruzioni: i commenti di questo script nominano tutto ciò che segue, e
    # un'asserzione sul testo grezzo passerebbe anche con le istruzioni cancellate
    script = "\n".join(
        riga for riga in ENTRYPOINT.read_text().splitlines()
        if riga.strip() and not riga.lstrip().startswith("#")
    )
    assert "alembic upgrade head" in script, (
        f"{ENTRYPOINT}: non esegue le migrazioni, quindi l'avvio non le applica"
    )
    assert 'exec "$@"' in script, (
        f"{ENTRYPOINT}: senza `exec \"$@\"` il comando del container (uvicorn) non "
        "parte, oppure parte come figlio e non riceve i segnali di arresto"
    )
    assert "set -e" in script, (
        f"{ENTRYPOINT}: senza `set -e` una migrazione fallita lascia partire uvicorn "
        "contro uno schema vecchio, che è il guasto da cui questo passo difende"
    )

    dockerfile = DOCKERFILE.read_text()
    assert "docker-entrypoint.sh" in dockerfile, (
        f"{DOCKERFILE}: nessun ENTRYPOINT che invochi {ENTRYPOINT.name}, quindi lo "
        "script non gira e le migrazioni tornano a essere un passo a mano"
    )
    assert "uvicorn" in dockerfile.split("CMD", 1)[-1], (
        f"{DOCKERFILE}: il CMD non lancia più uvicorn"
    )


@pytest.mark.parametrize("nome_file", COMPOSE_FILES)
def test_il_backend_parte_solo_con_il_database_sano(nome_file):
    """Corollario delle migrazioni all'avvio: `alembic` ha bisogno di un database su.

    Senza l'healthcheck sul servizio db e la condizione sul backend, all'avvio di uno
    stack nuovo il backend parte mentre initdb è ancora in corso e la migrazione muore
    sulla connessione rifiutata. In produzione il `restart: unless-stopped` lo
    rianimerebbe, cioè lo stesso risultato con in mezzo un crash-loop da leggere.
    """
    servizi = yaml.safe_load((REPO_ROOT / nome_file).read_text())["services"]

    assert "healthcheck" in servizi["db"], (
        f"{nome_file}: il servizio db non ha healthcheck, quindi "
        "`condition: service_healthy` non può funzionare"
    )
    dipendenze = servizi["backend"]["depends_on"]
    assert isinstance(dipendenze, dict) and dipendenze.get("db", {}).get(
        "condition"
    ) == "service_healthy", (
        f"{nome_file}: il backend dipende dal db come {dipendenze!r}, non con "
        "`condition: service_healthy`"
    )


@pytest.mark.parametrize("nome_file", COMPOSE_FILES)
def test_il_backend_dichiara_quando_e_pronto(nome_file):
    """`up -d --wait` è ciò che rende sicura la semina subito dopo, e vuole un healthcheck.

    Il README lo usa in tutti e tre gli avvii: senza healthcheck sul backend, `--wait`
    non ha niente da aspettare e `exec ... app.cli.seed` può arrivare mentre le
    migrazioni sono ancora in corso.
    """
    backend = yaml.safe_load((REPO_ROOT / nome_file).read_text())["services"]["backend"]
    assert "healthcheck" in backend, f"{nome_file}: il servizio backend non ha healthcheck"
    assert "health" in " ".join(backend["healthcheck"]["test"]), (
        f"{nome_file}: l'healthcheck del backend non interroga /api/v1/health: "
        f"{backend['healthcheck']['test']!r}"
    )
@pytest.mark.parametrize("nome_file", COMPOSE_FILES)
def test_la_cache_del_modello_vive_in_un_volume(nome_file):
    """Con INSTALL_EMBEDDINGS=1 il modello non deve riscaricarsi a ogni ricostruzione.

    Senza un volume la cache di Hugging Face sta nello strato scrivibile del
    container, che `up -d --build` butta via: ~500 MB riscaricati dopo ogni `git
    pull`, e il README che promette «al primo uso». Il bersaglio è /root/.cache perché
    l'immagine non dichiara USER, quindi il processo gira come root e HOME è /root.
    """
    backend = yaml.safe_load((REPO_ROOT / nome_file).read_text())["services"]["backend"]
    bersagli = [voce.split(":")[1] for voce in backend["volumes"] if ":" in voce]
    assert any(b.startswith("/root/.cache") for b in bersagli), (
        f"{nome_file}: nessun volume sulla cache del modello; montaggi {bersagli!r}. "
        "Con INSTALL_EMBEDDINGS=1 il modello si riscarica a ogni `up -d --build`."
    )
