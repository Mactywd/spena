#!/usr/bin/env bash
# Imposta la password d'accesso di spena: la chiede due volte senza mostrarla, ne
# calcola l'hash argon2 nel container del backend e lo scrive in password.env, nella
# radice del repo, leggibile solo dal proprietario.
#
# Il file Compose è un argomento obbligatorio, senza default. Sul server un default su
# docker-compose.yml sarebbe il trabocchetto della terza lezione di CLAUDE.md: i due
# file condividono il nome di progetto `spena`, e un comando sul file sbagliato tocca
# lo stack sbagliato.
#
# L'hash va in password.env e non in .env: Compose legge .env anche per sostituire i
# `${...}` dei file Compose, e lì `format: raw` non vale. I `$` dell'hash diventavano
# avvisi come `The "argon2id" variable is not set`, con dei pezzi dell'hash, a ogni
# comando. password.env è solo un `env_file` in forma lunga con `format: raw`, che non
# entra nella sostituzione.
#
# Lo script non riavvia niente: alla fine dice il comando da lanciare.
#
#   sul server:  ./scripts/imposta-password.sh docker-compose.prod.yml
#   in locale:   ./scripts/imposta-password.sh docker-compose.yml
set -euo pipefail
cd "$(dirname "$0")/.."

uso() {
  {
    echo "Uso: scripts/imposta-password.sh <file compose>"
    echo "  sul server:  ./scripts/imposta-password.sh docker-compose.prod.yml"
    echo "  in locale:   ./scripts/imposta-password.sh docker-compose.yml"
  } >&2
  exit 2
}

[ "$#" -eq 1 ] || uso
file=$1
[ -f "$file" ] || uso

# Con l'hash ancora in .env, il `docker compose run` qui sotto stamperebbe proprio gli
# avvisi con i pezzi dell'hash che questo script serve a togliere: ci si ferma prima.
# La riga non si stampa mai; una riga vuota (dal vecchio .env.example) non conta.
if [ -f .env ] && grep -qE '^[[:space:]]*(export[[:space:]]+)?APP_PASSWORD_HASH=.+' .env; then
  {
    echo "In .env c'è ancora APP_PASSWORD_HASH."
    echo "Compose legge .env anche per sostituire i \${...} dei file Compose, e ne"
    echo "stampa dei pezzi negli avvisi. Toglila prima, poi rilancia lo script:"
    echo "  sed -i -E '/^[[:space:]]*(export[[:space:]]+)?APP_PASSWORD_HASH=/d' .env"
  } >&2
  exit 1
fi

# Il prompt di `read -p` va su stderr, e solo davanti a un terminale.
IFS= read -rsp "Nuova password: " pw || true
echo >&2
IFS= read -rsp "Ripetila: " pw2 || true
echo >&2
if [ -z "$pw" ]; then
  echo "La password è vuota: password.env non è stato toccato." >&2
  exit 1
fi
if [ "$pw" != "$pw2" ]; then
  echo "Le due password sono diverse: password.env non è stato toccato." >&2
  exit 1
fi

# L'immagine si costruisce prima, a parte, con il progresso su stderr. Se manca (il
# primo giro dopo un deploy col backend cambiato), `docker compose run` la costruisce
# da sé e manda il progresso di BuildKit su stdout, davanti all'hash: lo si
# catturerebbe insieme all'hash (misurato: 46 righe), e il controllo qui sotto lo
# rifiuterebbe come se il container avesse sbagliato. Con l'immagine già pronta il
# `build` non rifà niente.
if ! docker compose -f "$file" build backend >&2; then
  echo "la costruzione dell'immagine del backend non è riuscita: password.env non è stato toccato" >&2
  exit 1
fi

# La password passa sullo standard input, senza a capo, e mai sulla riga di comando:
# così non finisce né nella cronologia della shell né in `ps`. `--entrypoint python`
# salta le migrazioni dell'entrypoint, `--no-deps` non avvia Postgres.
PROGRAMMA='import sys
from app.core.security import hash_password
print(hash_password(sys.stdin.read()))'
errore="il container non ha restituito un hash argon2: password.env non è stato toccato"
# Dentro un `if !`, così un errore di Compose non fa uscire lo script (set -e) senza
# il messaggio.
if ! hash=$(printf '%s' "$pw" | docker compose -f "$file" run --rm -T --no-deps --entrypoint python backend -c "$PROGRAMMA"); then
  echo "$errore" >&2
  exit 1
fi
case $hash in
  *$'\n'*) echo "$errore" >&2; exit 1 ;;
  "\$argon2id\$"*) ;;
  *) echo "$errore" >&2; exit 1 ;;
esac

# Sostituzione atomica: un password.env vecchio resta intero finché il nuovo non è
# pronto, e il temporaneo non resta in giro se qualcosa si interrompe.
umask 077
tmp=$(mktemp password.env.XXXXXX)
trap 'rm -f "$tmp"' EXIT
printf 'APP_PASSWORD_HASH=%s\n' "$hash" > "$tmp"
mv "$tmp" password.env

echo "password.env scritto: lo legge solo il proprietario."
echo "Vale dal prossimo avvio del backend:"
echo "  docker compose -f $file up -d --wait --wait-timeout 120 --force-recreate backend"
echo "Lo script ha costruito l'immagine del backend dal codice di questa cartella."
echo "Se non è il codice che gira, al posto del riavvio fai il deploy completo:"
echo "  docker compose -f $file up -d --build --wait"
