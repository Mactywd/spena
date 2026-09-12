#!/bin/sh
# Spec §13: «Le migrazioni Alembic girano all'avvio del backend».
#
# Prima non giravano: il Dockerfile lanciava uvicorn e nient'altro, e il passo stava
# solo nel README. La conseguenza arriva tutta insieme il giorno della prima
# migrazione dopo la 0003: `git pull` più `up -d --build` e il backend serve contro
# uno schema vecchio, con ogni chiamata a 500, finché il proprietario non si ricorda
# del comando.
#
# `set -e` è la metà che conta: se la migrazione fallisce il container muore invece di
# servire contro uno schema sbagliato. Su un'app a un utente e un'istanza non c'è il
# problema di concorrenza che rende questa scelta discutibile altrove — e il servizio
# `db` ha un healthcheck con `condition: service_healthy`, quindi qui Postgres accetta
# già connessioni.
set -e

alembic upgrade head

exec "$@"
