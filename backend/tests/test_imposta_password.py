"""scripts/imposta-password.sh, provato dal vero ma senza Docker.

Si prova lo script vero, copiato in una radice finta in `tmp_path`: lo script fa `cd`
nella cartella sopra la sua e scrive `password.env` lì, quindi lanciato dal suo posto
toccherebbe la radice vera del repo. La copia è fatta con `shutil.copy2`, che conserva
i permessi: un test controlla anche che lo script vero sia eseguibile.

Al posto di Docker c'è un `docker` finto in testa al `PATH`, che registra gli argomenti
e lo standard input e risponde con un hash finto (o con quello che il test gli chiede).
La suite non chiama mai Docker: il giro col container vero, che calcola un hash che il
backend poi verifica, è il Task 4 del piano 2026-11-18-hash-password.

Nessun test stampa l'hash o la password: le asserzioni li cercano nell'output solo per
dire che non ci sono.
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_SCRIPT = REPO_ROOT / "scripts" / "imposta-password.sh"
HASH_FINTO = "$argon2id$v=19$m=65536,t=3,p=4$c2FsZS1maW50bw$aGFzaC1maW50by1kZWxsYS1zdWl0ZQ"
FAKE_DOCKER = """#!/usr/bin/env bash
printf '%s\\n' "$@" > "$FAKE_DIR/args"
cat > "$FAKE_DIR/stdin"
printf '%s\\n' "$FAKE_OUTPUT"
exit "${FAKE_EXIT:-0}"
"""


@pytest.fixture
def radice(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy2(REAL_SCRIPT, repo / "scripts" / "imposta-password.sh")
    (repo / "docker-compose.yml").write_text("")
    (repo / "docker-compose.prod.yml").write_text("")
    (repo / ".env").write_text("SESSION_SECRET=x\n")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(FAKE_DOCKER)
    docker.chmod(0o755)

    fake_dir = tmp_path / "fake"
    fake_dir.mkdir()
    return repo, fake_dir


def lancia(
    radice: tuple[Path, Path],
    *args: str,
    stdin: str = "segreta\nsegreta\n",
    output: str = HASH_FINTO,
    exit_code: int = 0,
) -> subprocess.CompletedProcess:
    repo, fake_dir = radice
    tmp_path = repo.parent
    env = {
        **os.environ,
        "PATH": f"{tmp_path / 'bin'}:{os.environ.get('PATH', '')}",
        "FAKE_DIR": str(fake_dir),
        "FAKE_OUTPUT": output,
        "FAKE_EXIT": str(exit_code),
    }
    return subprocess.run(
        [repo / "scripts" / "imposta-password.sh", *args],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )


def resti_temporanei(repo: Path) -> list[Path]:
    return list(repo.glob("password.env.*"))


def test_scrive_password_env_con_lhash_e_i_permessi_600(radice):
    repo, _ = radice
    assert os.access(REAL_SCRIPT, os.X_OK)

    r = lancia(radice, "docker-compose.yml")

    assert r.returncode == 0
    password_env = repo / "password.env"
    assert password_env.read_text() == f"APP_PASSWORD_HASH={HASH_FINTO}\n"
    assert stat.S_IMODE(password_env.stat().st_mode) == 0o600
    assert resti_temporanei(repo) == []


def test_lhash_si_calcola_nel_container_del_file_indicato(radice):
    _, fake_dir = radice

    r = lancia(radice, "docker-compose.prod.yml")

    assert r.returncode == 0
    args = (fake_dir / "args").read_text().split("\n")
    attesi = [
        "compose", "-f", "docker-compose.prod.yml", "run", "--rm", "-T", "--no-deps",
        "--entrypoint", "python", "backend", "-c",
    ]
    assert args[: len(attesi)] == attesi
    # Il programma dopo `-c` occupa più righe: sono tutte quelle che restano.
    programma = "\n".join(args[len(attesi):])
    assert "hash_password" in programma
    assert "sys.stdin" in programma
    # La password arriva sullo standard input, senza a capo, e non sulla riga di comando.
    assert (fake_dir / "stdin").read_text() == "segreta"
    assert "segreta" not in (fake_dir / "args").read_text()


def test_non_stampa_ne_lhash_ne_la_password(radice):
    r = lancia(radice, "docker-compose.yml")

    assert r.returncode == 0
    out = r.stdout + r.stderr
    assert HASH_FINTO not in out
    assert "c2FsZS1maW50bw" not in out  # il sale
    assert "segreta" not in out
    # Il messaggio finale dice il comando di riavvio con il file passato.
    assert "docker-compose.yml" in out


@pytest.mark.parametrize("args", [(), ("non-esiste.yml",)], ids=["nessun-argomento", "file-assente"])
def test_senza_il_file_compose_si_rifiuta_e_non_chiama_docker(radice, args):
    repo, fake_dir = radice

    r = lancia(radice, *args)

    assert r.returncode == 2
    assert "Uso:" in r.stderr
    assert not (fake_dir / "args").exists()
    assert not (repo / "password.env").exists()


def test_con_lhash_ancora_in_env_si_rifiuta_prima_di_compose(radice):
    repo, fake_dir = radice
    (repo / ".env").write_text(f"SESSION_SECRET=x\nAPP_PASSWORD_HASH={HASH_FINTO}\n")

    r = lancia(radice, "docker-compose.yml")

    assert r.returncode == 1
    assert not (fake_dir / "args").exists()
    assert "APP_PASSWORD_HASH" in r.stderr
    assert "sed -i '/^APP_PASSWORD_HASH=/d' .env" in r.stderr
    assert HASH_FINTO not in r.stdout + r.stderr
    assert not (repo / "password.env").exists()


def test_una_riga_vuota_in_env_non_ferma(radice):
    repo, _ = radice
    # Il `.env` copiato dal vecchio `.env.example` ha la riga, vuota.
    (repo / ".env").write_text("SESSION_SECRET=x\nAPP_PASSWORD_HASH=\n")

    r = lancia(radice, "docker-compose.yml")

    assert r.returncode == 0
    assert (repo / "password.env").read_text() == f"APP_PASSWORD_HASH={HASH_FINTO}\n"


@pytest.mark.parametrize("stdin", ["\n\n", "una\naltra\n"], ids=["vuote", "diverse"])
def test_password_vuote_o_diverse_non_scrivono_niente(radice, stdin):
    repo, fake_dir = radice

    r = lancia(radice, "docker-compose.yml", stdin=stdin)

    assert r.returncode == 1
    assert not (fake_dir / "args").exists()
    assert not (repo / "password.env").exists()


@pytest.mark.parametrize(
    ("output", "exit_code"),
    [("Traceback (most recent call last):", 0), ("", 1)],
    ids=["non-argon2", "compose-fallito"],
)
def test_una_risposta_non_argon2_lascia_password_env_comera(radice, output, exit_code):
    repo, _ = radice
    password_env = repo / "password.env"
    password_env.write_text("APP_PASSWORD_HASH=quello-di-prima\n")

    r = lancia(radice, "docker-compose.yml", output=output, exit_code=exit_code)

    assert r.returncode == 1
    assert password_env.read_text() == "APP_PASSWORD_HASH=quello-di-prima\n"
    assert resti_temporanei(repo) == []
