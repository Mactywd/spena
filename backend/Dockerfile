FROM python:3.12-slim

WORKDIR /app

# `anthropic` si installa sempre. Non è opzionale nella pratica: la stesura AI è
# una funzionalità della v1 con uno schermo suo, e senza il pacchetto quello schermo
# risponde «La stesura AI non è disponibile» con qualunque chiave configurata. È puro
# Python e costa poco.
#
# `sentence-transformers` no, e non per gusto: trascina torch, che pesa GB (la spec
# §5 ne stimava 500 MB: è una stima sbagliata). L'applicazione è progettata per
# funzionare senza — la ricerca resta quella testuale su pg_trgm, che è la
# degradazione documentata nella spec §11 — quindi l'extra si accende quando lo si
# vuole, da un posto solo: `INSTALL_EMBEDDINGS=1` in `.env`, che i file Compose
# passano qui come argomento di build. Vedi la riga `EMBEDDING_BACKEND` del README.
ARG INSTALL_EMBEDDINGS=0

COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir -e ".[ai]" \
 && if [ "$INSTALL_EMBEDDINGS" = "1" ]; then \
      pip install --no-cache-dir -e ".[embeddings]"; \
    fi

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
