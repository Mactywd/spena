FROM python:3.12-slim

WORKDIR /app

# `sentence-transformers` non si installa per default, e non per gusto: trascina torch,
# che pesa GB (la spec §5 ne stimava 500 MB: è una stima sbagliata). L'applicazione è
# progettata per funzionare senza — la ricerca resta quella testuale su pg_trgm, che è
# la degradazione documentata nella spec §11 — quindi l'extra si accende quando lo si
# vuole, da un posto solo: `INSTALL_EMBEDDINGS=1` in `.env`, che i file Compose passano
# qui come argomento di build. Vedi la riga `EMBEDDING_BACKEND` del README.
#
# Il client del modello linguistico è l'SDK `anthropic`, dipendenza di base fissata nel
# `pyproject.toml`: niente extra. È la lezione della prima volta, quando `anthropic`
# stava fra gli extra e mancava dall'immagine, e la stesura AI rispondeva «pacchetto non
# installato» a ogni chiamata.
# Anche l'Agent SDK di Claude è una dipendenza di base, e il suo binario arriva con la
# ruota di pip: nessun Node nell'immagine.
ARG INSTALL_EMBEDDINGS=0

COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir -e . \
 && if [ "$INSTALL_EMBEDDINGS" = "1" ]; then \
      pip install --no-cache-dir -e ".[embeddings]"; \
    fi

COPY . .

EXPOSE 8000

# Invocato con `sh` di proposito: in sviluppo /app è un bind mount di ./backend,
# quindi a girare è il file dell'host e il bit di esecuzione impostato qui non
# conterebbe niente.
ENTRYPOINT ["sh", "./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
