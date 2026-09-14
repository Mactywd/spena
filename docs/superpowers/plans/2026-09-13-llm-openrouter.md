# LLM su OpenRouter e riconoscimento degli ingredienti — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** sostituire Anthropic con OpenRouter (`google/gemma-4-26b-a4b-it`) e far decidere all'AI i termini sconosciuti dell'import, con una revisione che permette di annullare qualunque sua decisione.

**Architecture:** un client HTTP solo (`services/llm.py`, su `httpx` già presente) che torna JSON validato da uno schema stretto. Sopra, `services/recipe_import/decide.py` fa una chiamata per termine in parallelo, una passata di collasso sui soli ingredienti da creare, e applica le scritture in sequenza. `services/recipe_import/undo.py` disfa una decisione rimettendo termine, alias, ingrediente e pagine come erano. Nessuna migrazione: `import_terms.decided_by` esiste già e accoglie `"ai"`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Postgres 16 (pgvector + pg_trgm), `httpx`, `respx` per i test di rete, React 19 + Vite + TypeScript, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-13-llm-openrouter-design.md`

## Global Constraints

Valgono per ogni task, sempre. Non si ripetono nei task.

- **Il modello è `google/gemma-4-26b-a4b-it`**, configurabile via `OPENROUTER_MODEL`.
- **Ogni richiesta a OpenRouter porta gli header `HTTP-Referer` e `X-Title`.** Il titolo è `Spena Import Ricette`. Un valore vuoto non si manda: l'header si omette.
- **Ogni richiesta porta `response_format` con `type: "json_schema"` e `strict: true`.** Vincolo dello strict mode: **ogni** proprietà dello schema deve comparire in `required`, e `additionalProperties` deve essere `false`. I campi che valgono per una sola azione si dichiarano nullable (`{"type": ["string", "null"]}`), non opzionali.
- **Ogni richiesta porta `provider: {"sort": "price", "require_parameters": true}`**, tranne quando `OPENROUTER_PROVIDER_ONLY` è valorizzata, e allora `{"only": [...], "require_parameters": true}`. `allow_fallbacks` non si tocca: il suo default `true` è la ragione per cui non pinniamo un provider.
- **Mai un vicolo cieco.** `LlmUnavailable` non fa fallire nessun comando e nessuna schermata: `import_gz` stampa la riga della coda ed esce con 0, le rotte rispondono `503` con «decidi a mano, la coda funziona», e la coda manuale resta identica.
- **Una risposta non verificabile non si applica.** `map` verso un ingrediente inesistente, `category` fuori dalle dodici, un `canonical` che nessuno ha proposto: si scarta e il termine resta `pending`. Il modello può sbagliare, non può scrivere spazzatura.
- **Nessuna migrazione Alembic.** Se ne nasce il bisogno, fermarsi: è il segnale che qualcosa si è allontanato dalla spec.
- **Niente quantità nei calcoli.** `quantity_text` è testo da mostrare. Regola fondante del progetto (CLAUDE.md).
- **Nessun valore nutrizionale dal modello.** Mai, in nessun prompt.
- **La suite non tocca la rete.** Open Food Facts e il modello girano su `respx` o su client finti iniettati. Test su Postgres vero via Compose, non SQLite.
- **Tutto il colore sta in `frontend/src/index.css`** dentro `@theme`. Nessuna schermata nomina un colore grezzo: `grep -rn "emerald\|neutral-" frontend/src` deve restare vuoto. I primitivi condivisi sono in `frontend/src/components/ui/`.
- **Il type check del frontend è `npm run typecheck` e `npm run build`.** `tsc --noEmit` su questo progetto esce sempre 0 e non prova niente (`frontend/tsconfig.json` è solution-style). Non usarlo mai come verifica.
- **Specifiche e commenti in italiano, identificatori in inglese.**
- **Ogni messaggio di commit finisce con la riga:**
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  ```
  Negli step sotto i comandi `git commit` sono scritti in breve: la riga di attribuzione va aggiunta comunque, sempre.
- **Comandi:** il backend si prova con `cd backend && .venv/bin/python -m pytest <path> -v`, con Postgres su tramite `docker compose up -d db`. Il frontend con `cd frontend && npx vitest run <path>`.

  > **Corretto il 2026-09-14.** Questa riga diceva `docker compose exec backend pytest
  > <path> -v`. Non gira: il Dockerfile installa solo `-e .` (più `[embeddings]` quando
  > acceso), mai l'extra `dev`, quindi `pytest` non è nell'immagine. Ogni task di questo
  > piano ha girato sull'host, che è quel che `README.md` documenta in «Test». I comandi
  > `Run:` scritti nei singoli task restano con la forma vecchia: sono il verbale di cosa
  > diceva il piano, non un comando da rilanciare.

---

## Struttura dei file

**Creati**

| File | Responsabilità |
|---|---|
| `backend/app/services/llm.py` | una chiamata a OpenRouter che torna un `dict` o solleva `LlmUnavailable`. Header, instradamento del provider, schema stretto. Non sa niente di ricette. |
| `backend/app/services/recipe_import/decide.py` | i prompt e gli schemi dei termini, la chiamata per termine, la passata di collasso, l'applicazione in sequenza. |
| `backend/app/services/recipe_import/undo.py` | disfare una decisione: termine, alias, ingrediente, pagine. |
| `backend/app/cli/llm_prices.py` | la tabella dei prezzi per provider e il costo delle due strategie. Strumento, non dipendenza del percorso caldo. |
| `frontend/src/features/recipe-import/DecidedTermRow.tsx` | una riga dell'elenco «Deciso dall'AI», con il suo «Annulla». |

**Modificati**

| File | Cosa cambia |
|---|---|
| `backend/app/core/config.py` | otto campi nuovi, `anthropic_api_key` via |
| `backend/app/repositories/ingredients.py` | `remember_alias`, `forget_alias`, `delete_ingredient_if_unused` |
| `backend/app/services/recipe_import/terms.py` | `propose_decisions` esce (va in `decide.py`); `sync_terms` resta identica |
| `backend/app/services/ai_recipes.py` | sul client nuovo; categoria proposta per ogni ingrediente |
| `backend/app/api/imports.py` | `?decided_by`, `/terms/decide` al posto di `/terms/proposals`, `/terms/{id}/undo`, alias condiviso |
| `backend/app/schemas/recipe_import.py` | `TermOut` cresce, `DecideRequest`/`DecideOut`/`UndoRequest`/`UndoOut`, `ProposalsRequest`/`ProposalOut`/`ProposalsOut` via |
| `backend/app/schemas/ai.py` | `proposed_category` |
| `backend/app/schemas/recipe.py` | `RecipeIngredientIn` accetta nome + categoria in luogo di `ingredient_id` |
| `backend/app/api/recipes.py` | creazione dell'ingrediente nella transazione della ricetta |
| `backend/app/cli/import_gz.py` | chiama `decide_terms` fra `sync_terms` e `materialize_ready` |
| `backend/pyproject.toml`, `backend/Dockerfile` | l'extra `ai` e `anthropic` escono |
| `backend/tests/test_image_dependencies.py` | riscritto su OpenRouter |
| `backend/tests/conftest.py` | il commento e la variabile neutralizzata |
| `.env.example`, `CLAUDE.md`, `README.md` | documentazione |
| `frontend/src/domain/types.ts` | `ImportTerm` cresce, `TermProposal` via, `DecidedTerm`, `UndoResult` |
| `frontend/src/features/recipe-import/api.ts` | `fetchTermProposals` → `decideWithAi`, `fetchDecidedTerms`, `undoTerm` |
| `frontend/src/features/recipe-import/ImportQueueScreen.tsx` | due elenchi; l'apparato delle proposte esce |
| `frontend/src/features/recipe-import/TermCard.tsx` | non riceve più `proposal`/`proposalsReady` |
| `frontend/src/features/ai-draft/AiDraftScreen.tsx` | «lo creo io: nome, categoria» |

---

## Preliminare: i client finti stanno in un modulo, non in un file di test

Cinque task hanno bisogno dello stesso client finto. **Non importarlo da un altro file di
test**: `backend/tests/` non ha `__init__.py` mentre `tests/services/`, `tests/api/`,
`tests/db/` e `tests/domain/` ce l'hanno, quindi pytest inserisce `tests/` in `sys.path`
e un `from tests.services.test_decide_one import FakeLlm` non risolve. Un modulo dentro
`tests/` invece si importa piano: `from llm_fakes import FakeLlm`.

Crea `backend/tests/llm_fakes.py` come primo passo del Task 5, e usalo da lì in avanti.

```python
"""I client finti per le chiamate all'LLM. La suite non tocca la rete.

Stanno qui e non in un file di test perché cinque file li usano, e perché
`backend/tests/` non è un package: importarli da un altro file di test non
risolverebbe. Questo modulo sì — pytest inserisce `tests/` in `sys.path`, dato che le
sottocartelle sono package e questa no.

Entrambi i finti sostituiscono `httpx.AsyncClient`, non il client di OpenRouter: il
codice sotto prova è `complete_json` per intero, header e corpo compresi. Un finto più
in alto lascerebbe fuori proprio le righe che nessun altro test attraversa.
"""

import json as _json

import httpx


class FakeLlm:
    """Risponde una cosa per volta, nell'ordine dato. Registra i corpi mandati.

    Una `Exception` fra i payload viene sollevata invece di risposta: è così che si
    prova la degradazione senza rete.
    """

    def __init__(self, *payloads: object) -> None:
        self._payloads = list(payloads)
        self.bodies: list[dict] = []

    async def post(self, url, json: dict, headers):  # noqa: A002
        self.bodies.append(json)
        payload = self._payloads.pop(0) if self._payloads else {}
        if isinstance(payload, Exception):
            raise payload
        text = payload if isinstance(payload, str) else _json.dumps(payload)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": text}}]},
            request=httpx.Request("POST", url),
        )

    async def aclose(self):
        return None


class ScriptedLlm:
    """Una risposta per ogni domanda, scelta guardando **cosa** la domanda chiede.

    Non una coda ordinata: il fan-out è parallelo e l'ordine di arrivo non è garantito.
    Una coda renderebbe il test sensibile a uno scheduling che non controlliamo, ed è il
    modo classico di scrivere un test che fallisce a caso.

    La domanda del collasso si riconosce dalla chiave `nuovi`; tutte le altre portano
    `termine`.
    """

    def __init__(self, per_term: dict[str, object], collapse: object | None = None) -> None:
        self._per_term = per_term
        self._collapse = collapse
        self.calls = 0
        self.bodies: list[dict] = []

    async def post(self, url, json: dict, headers):  # noqa: A002
        self.calls += 1
        self.bodies.append(json)
        question = _json.loads(json["messages"][1]["content"])
        if "nuovi" in question:
            payload = self._collapse if self._collapse is not None else {"groups": []}
        else:
            payload = self._per_term[question["termine"]]
        if isinstance(payload, Exception):
            raise payload
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": _json.dumps(payload)}}]},
            request=httpx.Request("POST", url),
        )

    async def aclose(self):
        return None


def llm_map(name: str) -> dict:
    """Il corpo di una risposta `map`, con i campi nulli che lo strict mode esige."""
    return {"action": "map", "ingredient": name, "name": None,
            "display_name": None, "category": None}


def llm_create(name: str, display_name: str, category: str) -> dict:
    return {"action": "create", "ingredient": None, "name": name,
            "display_name": display_name, "category": category}


LLM_IGNORE = {"action": "ignore", "ingredient": None, "name": None,
              "display_name": None, "category": None}
```

Verifica che risolva da entrambe le profondità, che è il punto:

```bash
docker compose exec backend python -c "import sys; sys.path.insert(0, 'tests'); import llm_fakes; print('ok')"
```

---

## Task 1: Configurazione

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Test: `backend/tests/test_settings_openrouter.py`

**Interfaces:**
- Consumes: nulla.
- Produces: su `Settings` — `openrouter_api_key: str | None`, `openrouter_model: str`, `openrouter_base_url: str`, `openrouter_app_title: str`, `openrouter_app_url: str`, `openrouter_provider_only: str`, `llm_timeout_seconds: float`, `llm_max_concurrency: int`. `anthropic_api_key` non esiste più.

- [ ] **Step 1: Scrivi il test che fallisce**

In `backend/tests/test_settings_openrouter.py`:

```python
"""Le impostazioni di OpenRouter: i default e il fatto che l'ambiente li scavalchi.

`get_settings` è memoizzata con `lru_cache`: senza `cache_clear` un test che imposta
una variabile leggerebbe l'istanza costruita da un test precedente, e passerebbe o
fallirebbe in base all'ordine di esecuzione.
"""

from app.core.config import get_settings


def test_i_default_sono_quelli_della_spec():
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.openrouter_api_key is None
        assert settings.openrouter_model == "google/gemma-4-26b-a4b-it"
        assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"
        assert settings.openrouter_app_title == "Spena Import Ricette"
        # vuota di proposito: il dominio dell'utente sta in .env, non nel codice
        assert settings.openrouter_app_url == ""
        assert settings.openrouter_provider_only == ""
        assert settings.llm_timeout_seconds == 60.0
        assert settings.llm_max_concurrency == 8
    finally:
        get_settings.cache_clear()


def test_lambiente_scavalca_i_default(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-5")
    monkeypatch.setenv("OPENROUTER_PROVIDER_ONLY", "darkbloom")
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "3")
    try:
        settings = get_settings()
        assert settings.openrouter_model == "anthropic/claude-sonnet-5"
        assert settings.openrouter_provider_only == "darkbloom"
        assert settings.llm_max_concurrency == 3
    finally:
        get_settings.cache_clear()


def test_anthropic_non_e_piu_unimpostazione():
    """La chiave di Anthropic esce da Settings, non resta come campo morto.

    Un campo che nessuno legge è peggio che assente: chi configura `.env` crede di
    aver acceso qualcosa.
    """
    get_settings.cache_clear()
    try:
        assert not hasattr(get_settings(), "anthropic_api_key")
    finally:
        get_settings.cache_clear()
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `docker compose exec backend pytest tests/test_settings_openrouter.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'openrouter_model'`, e il terzo test fallisce perché `anthropic_api_key` c'è ancora.

- [ ] **Step 3: Modifica `Settings`**

In `backend/app/core/config.py`, sostituisci la riga `anthropic_api_key: str | None = None` con:

```python
    # OpenRouter è l'unico fornitore di LLM dell'applicazione. Un secondo fornitore
    # dietro un'interfaccia scelta da una variabile (come EMBEDDING_BACKEND) non
    # girerebbe mai in produzione, e sarebbe il difetto in cima a CLAUDE.md. Quel che
    # resta configurabile è il modello: OpenRouter fa da proxy anche a Claude, quindi
    # passare a un modello grosso è questa riga, non un secondo client.
    openrouter_api_key: str | None = None
    openrouter_model: str = "google/gemma-4-26b-a4b-it"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Identificano l'app nelle classifiche e nei consumi di OpenRouter. Il titolo ha
    # un default perché è una costante del progetto; l'indirizzo no, perché è il
    # dominio di chi installa e nel codice non ci sta.
    openrouter_app_title: str = "Spena Import Ricette"
    openrouter_app_url: str = ""
    # Vuota: instradamento per prezzo fra i provider che sanno onorare lo schema.
    # Valorizzata (lista separata da virgole): scavalco manuale, e si perde il
    # failover automatico. Vedi `python -m app.cli.llm_prices`.
    openrouter_provider_only: str = ""
    # 60 e non i 3 di Open Food Facts: un MoE su una domanda con l'anagrafica intera
    # dentro è lento, e un timeout troppo corto si presenta come «decidi a mano».
    llm_timeout_seconds: float = 60.0
    llm_max_concurrency: int = 8
```

- [ ] **Step 4: Esegui il test e verifica che passi**

Run: `docker compose exec backend pytest tests/test_settings_openrouter.py -v`
Expected: PASS, 3 test.

- [ ] **Step 5: Aggiorna `.env.example`**

Sostituisci la riga `ANTHROPIC_API_KEY=` con:

```
# La chiave di OpenRouter, che serve al riconoscimento degli ingredienti dell'import e
# alla stesura AI delle ricette. Senza, tutto continua a funzionare a mano: la coda si
# decide a tocchi e lo schermo della stesura AI dice che non è disponibile.
OPENROUTER_API_KEY=
# Il modello. OpenRouter fa da proxy a mezzo mondo, Claude compreso: se le risposte di
# Gemma deludono, qui si scrive `anthropic/claude-sonnet-5` e non cambia altro.
OPENROUTER_MODEL=google/gemma-4-26b-a4b-it
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
# Header HTTP-Referer e X-Title: identificano l'app nelle classifiche e nei consumi di
# OpenRouter. L'indirizzo è il tuo dominio; vuoto, l'header si omette.
OPENROUTER_APP_TITLE=Spena Import Ricette
OPENROUTER_APP_URL=
# Vuota, il provider più economico che sappia rispettare lo schema JSON viene scelto da
# OpenRouter, con caduta automatica sul successivo. Valorizzata (lista separata da
# virgole, es. `darkbloom`), pinni a mano e perdi quella caduta. Per decidere:
# `docker compose exec backend python -m app.cli.llm_prices`.
OPENROUTER_PROVIDER_ONLY=
LLM_TIMEOUT_SECONDS=60
# Quante domande in volo nel riconoscimento parallelo dei termini.
LLM_MAX_CONCURRENCY=8
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/config.py .env.example backend/tests/test_settings_openrouter.py
git commit -m "feat: le impostazioni di OpenRouter, e ANTHROPIC_API_KEY esce"
```

---

## Task 2: Il client di OpenRouter

**Files:**
- Create: `backend/app/services/llm.py`
- Test: `backend/tests/services/test_llm.py`

**Interfaces:**
- Consumes: `Settings` del Task 1.
- Produces:
  - `class LlmUnavailable(Exception)`
  - `def build_headers() -> dict[str, str]`
  - `def build_provider_preferences() -> dict[str, object]`
  - `async def complete_json(system: str, user: str, schema: dict, schema_name: str, max_tokens: int, client: httpx.AsyncClient | None = None) -> dict`

- [ ] **Step 1: Scrivi il test che fallisce**

In `backend/tests/services/test_llm.py`:

```python
"""Il client di OpenRouter: la richiesta che costruisce e i modi in cui degrada.

`respx` intercetta httpx senza rete: è già fra le dipendenze `dev`. I test sulla
**forma della richiesta** sono quelli che contano di più — sono l'unico posto in cui
si dimostra che gli header di attribuzione, lo schema stretto e l'instradamento per
prezzo arrivano davvero a OpenRouter. Nessun test che inietta un client finto potrebbe
vederlo.
"""

import json

import httpx
import pytest
import respx

from app.core.config import get_settings
from app.services.llm import LlmUnavailable, complete_json

URL = "https://openrouter.ai/api/v1/chat/completions"

SCHEMA = {
    "type": "object",
    "properties": {"esito": {"type": "string"}},
    "required": ["esito"],
    "additionalProperties": False,
}


def risposta(contenuto: dict) -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"message": {"content": json.dumps(contenuto)}}]}
    )


@pytest.fixture
def con_chiave(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    monkeypatch.setenv("OPENROUTER_APP_URL", "https://esempio.invalid")
    yield
    get_settings.cache_clear()


async def test_una_risposta_valida_torna_il_dizionario(con_chiave):
    async with respx.mock:
        respx.post(URL).mock(return_value=risposta({"esito": "va bene"}))
        assert await complete_json(
            system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
        ) == {"esito": "va bene"}


async def test_la_richiesta_porta_attribuzione_schema_e_instradamento(con_chiave):
    async with respx.mock:
        route = respx.post(URL).mock(return_value=risposta({"esito": "ok"}))
        await complete_json(
            system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
        )

    richiesta = route.calls.last.request
    assert richiesta.headers["authorization"] == "Bearer chiave-finta"
    assert richiesta.headers["x-title"] == "Spena Import Ricette"
    assert richiesta.headers["http-referer"] == "https://esempio.invalid"

    corpo = json.loads(richiesta.content)
    assert corpo["model"] == "google/gemma-4-26b-a4b-it"
    formato = corpo["response_format"]
    assert formato["type"] == "json_schema"
    assert formato["json_schema"]["strict"] is True
    assert formato["json_schema"]["name"] == "prova"
    assert formato["json_schema"]["schema"] == SCHEMA
    # require_parameters è la riga che porta il peso: quattro degli undici endpoint di
    # questo modello non supportano structured_outputs, e uno di quelli è il secondo
    # più economico. Senza il flag, l'ordinamento per prezzo ci manda addosso.
    assert corpo["provider"] == {"sort": "price", "require_parameters": True}
    # allow_fallbacks non si manda: il suo default `true` è la ragione per cui non
    # pinniamo un provider, e scriverlo esplicitamente inviterebbe a cambiarlo
    assert "allow_fallbacks" not in corpo["provider"]


async def test_app_url_vuota_omette_lheader_invece_di_mandarlo_vuoto(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    monkeypatch.setenv("OPENROUTER_APP_URL", "")
    try:
        async with respx.mock:
            route = respx.post(URL).mock(return_value=risposta({"esito": "ok"}))
            await complete_json(
                system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
            )
        assert "http-referer" not in route.calls.last.request.headers
    finally:
        get_settings.cache_clear()


async def test_provider_only_valorizzata_pinna_e_non_ordina(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    monkeypatch.setenv("OPENROUTER_PROVIDER_ONLY", "darkbloom, deepinfra")
    try:
        async with respx.mock:
            route = respx.post(URL).mock(return_value=risposta({"esito": "ok"}))
            await complete_json(
                system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
            )
        corpo = json.loads(route.calls.last.request.content)
        assert corpo["provider"] == {
            "only": ["darkbloom", "deepinfra"], "require_parameters": True
        }
    finally:
        get_settings.cache_clear()


async def test_senza_chiave_non_parte_nessuna_richiesta(monkeypatch):
    """La degradazione dichiarata, e prima della rete: non si spreca un giro."""
    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    try:
        async with respx.mock:
            route = respx.post(URL).mock(return_value=risposta({"esito": "ok"}))
            with pytest.raises(LlmUnavailable, match="OPENROUTER_API_KEY"):
                await complete_json(
                    system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
                )
            assert route.call_count == 0
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("codice", [400, 402, 429, 500, 503])
async def test_ogni_codice_derrore_diventa_llm_unavailable(con_chiave, codice):
    async with respx.mock:
        respx.post(URL).mock(return_value=httpx.Response(codice, text="no"))
        with pytest.raises(LlmUnavailable, match=str(codice)):
            await complete_json(
                system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
            )


async def test_un_corpo_senza_choices_diventa_llm_unavailable(con_chiave):
    async with respx.mock:
        respx.post(URL).mock(return_value=httpx.Response(200, json={"error": "boh"}))
        with pytest.raises(LlmUnavailable):
            await complete_json(
                system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
            )


async def test_un_contenuto_non_json_diventa_llm_unavailable(con_chiave):
    """Con lo schema stretto non dovrebbe capitare, e se capita non deve esplodere."""
    async with respx.mock:
        respx.post(URL).mock(
            return_value=httpx.Response(
                200, json={"choices": [{"message": {"content": "mi dispiace, ma"}}]}
            )
        )
        with pytest.raises(LlmUnavailable):
            await complete_json(
                system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
            )


async def test_un_json_che_non_e_un_oggetto_diventa_llm_unavailable(con_chiave):
    async with respx.mock:
        respx.post(URL).mock(
            return_value=httpx.Response(
                200, json={"choices": [{"message": {"content": "[1, 2, 3]"}}]}
            )
        )
        with pytest.raises(LlmUnavailable, match="oggetto JSON"):
            await complete_json(
                system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
            )


async def test_un_timeout_diventa_llm_unavailable(con_chiave):
    async with respx.mock:
        respx.post(URL).mock(side_effect=httpx.ReadTimeout("troppo lento"))
        with pytest.raises(LlmUnavailable):
            await complete_json(
                system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
            )
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `docker compose exec backend pytest tests/services/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.llm'`.

- [ ] **Step 3: Scrivi `backend/app/services/llm.py`**

```python
"""Una chiamata a un LLM, via OpenRouter, che torna JSON o solleva.

Un fornitore solo e un client solo. Non c'è un'interfaccia a due implementazioni
scelta da una variabile, come per gli embedding: il secondo percorso non girerebbe
mai in produzione, e sarebbe esattamente il difetto in cima a CLAUDE.md — un test che
costruisce il proprio oggetto non prova quello che gira. Quel che resta configurabile
è il modello, e poiché OpenRouter fa da proxy anche a Claude, passare a un modello
grosso è una riga di `.env`.

Questo file non sa niente di ricette, di ingredienti e di import: prende un prompt e
uno schema, torna un dizionario. È ciò che permette di provarlo per intero contro
`respx`, senza database.
"""

import json
from typing import Any

import httpx

from app.core.config import get_settings


class LlmUnavailable(Exception):
    """Modello non raggiungibile o risposta inutilizzabile.

    Non è un errore da propagare: chi chiama la traduce in «decidi a mano», che è
    sempre possibile. Vedi la regola «mai un vicolo cieco» in CLAUDE.md.
    """


def build_headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise LlmUnavailable("OPENROUTER_API_KEY non configurata")
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    # Identificano l'app nelle classifiche e nei consumi di OpenRouter: è come si
    # distingue questo traffico da qualunque altro sulla stessa chiave. Opzionali per
    # loro, obbligatori per noi — ma un header vuoto non è attribuzione, è rumore.
    if settings.openrouter_app_url:
        headers["HTTP-Referer"] = settings.openrouter_app_url
    if settings.openrouter_app_title:
        headers["X-Title"] = settings.openrouter_app_title
    return headers


def build_provider_preferences() -> dict[str, Any]:
    """Il provider più economico che sappia onorare lo schema.

    `require_parameters` porta il peso. Misurato il 2026-09-13 su
    `/models/google/gemma-4-26b-a4b-it/endpoints`: quattro degli undici endpoint non
    supportano `structured_outputs`, e uno di quelli (DekaLLM, 0,060 contro i 0,042 di
    Darkbloom) è il **secondo più economico**. Senza il flag, l'ordinamento per prezzo
    instrada verso un endpoint che non può rispettare `response_format`.

    `sort: "price"` spegne il bilanciamento di default, che pesa sull'inverso del
    quadrato del prezzo e quindi a volte sceglie un endpoint caro.

    `allow_fallbacks` non si manda: il suo default è `true`, cioè un errore o un rate
    limit sul primo scende al secondo più economico da sé. È esattamente ciò che si
    perde pinnando un provider a mano, ed è il motivo per cui `openrouter_provider_only`
    nasce vuota.
    """
    settings = get_settings()
    only = [name.strip() for name in settings.openrouter_provider_only.split(",") if name.strip()]
    if only:
        return {"only": only, "require_parameters": True}
    return {"sort": "price", "require_parameters": True}


async def complete_json(
    *,
    system: str,
    user: str,
    schema: dict[str, Any],
    schema_name: str,
    max_tokens: int,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Una risposta JSON conforme a `schema`, o `LlmUnavailable`.

    Lo schema stretto è ciò che rende inutile qualunque scrostatore di blocchi di
    codice: la risposta è JSON o è un errore. Vincolo dello strict mode da rispettare
    negli schemi che si passano qui — ogni proprietà deve stare in `required` e
    `additionalProperties` deve essere `false` — quindi i campi che valgono per una
    sola azione si dichiarano nullable, non opzionali.

    `client` si passa quando il chiamante ne ha già uno aperto: il riconoscimento
    parallelo fa N chiamate insieme, e aprire N connessioni separate sarebbe uno
    spreco che il semaforo non compensa.
    """
    settings = get_settings()
    headers = build_headers()  # prima della rete: senza chiave non si spreca un giro
    body = {
        "model": settings.openrouter_model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": schema},
        },
        "provider": build_provider_preferences(),
    }
    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"

    owned = client is None
    api = client if client is not None else httpx.AsyncClient(timeout=settings.llm_timeout_seconds)
    try:
        response = await api.post(url, json=body, headers=headers)
        if response.status_code >= 400:
            raise LlmUnavailable(
                f"OpenRouter ha risposto {response.status_code}: {response.text[:200]}"
            )
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise LlmUnavailable("la risposta non è un oggetto JSON")
        return parsed
    except LlmUnavailable:
        raise
    except Exception as exc:  # rete, timeout, corpo senza choices, JSON malformato
        raise LlmUnavailable(str(exc)) from exc
    finally:
        if owned:
            await api.aclose()


def open_client() -> httpx.AsyncClient:
    """Un client col timeout configurato, per chi fa più chiamate di seguito."""
    return httpx.AsyncClient(timeout=get_settings().llm_timeout_seconds)
```

- [ ] **Step 4: Esegui il test e verifica che passi**

Run: `docker compose exec backend pytest tests/services/test_llm.py -v`
Expected: PASS, 14 test (i cinque codici d'errore sono parametrizzati).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm.py backend/tests/services/test_llm.py
git commit -m "feat: il client di OpenRouter, con schema stretto e instradamento per prezzo"
```

---

## Task 3: Il CLI dei prezzi

**Files:**
- Create: `backend/app/cli/llm_prices.py`
- Test: `backend/tests/test_llm_prices_cli.py`

**Interfaces:**
- Consumes: `Settings` (Task 1).
- Produces:
  - `@dataclass(frozen=True) class Endpoint` con `provider: str`, `prompt: float`, `completion: float`, `cache_read: float | None`, `structured: bool`
  - `def parse_endpoints(payload: dict) -> list[Endpoint]`
  - `def batch_cost(endpoint: Endpoint, *, calls: int, prefix_tokens: int, suffix_tokens: int, output_tokens: int) -> float`
  - `def usable(endpoints: list[Endpoint]) -> list[Endpoint]` — solo quelli con `structured`, ordinati per prezzo
  - `async def main() -> None`

- [ ] **Step 1: Scrivi il test che fallisce**

In `backend/tests/test_llm_prices_cli.py`:

```python
"""Il calcolo dei prezzi: l'ordinamento, l'esclusione e il costo di un lotto.

Serve ad accorgersi del giorno in cui il compromesso input/output comparirà davvero —
oggi Darkbloom è il più economico su entrambe le voci, quindi qualunque formula dà lo
stesso vincitore, e la documentazione di OpenRouter non dichiara la sua.
"""

from app.cli.llm_prices import Endpoint, batch_cost, parse_endpoints, usable

PAYLOAD = {
    "data": {
        "endpoints": [
            {
                "provider_name": "Darkbloom",
                "pricing": {"prompt": "0.000000042", "completion": "0.00000022"},
                "supported_parameters": ["response_format", "structured_outputs"],
            },
            {
                "provider_name": "DekaLLM",
                "pricing": {"prompt": "0.00000006", "completion": "0.00000033"},
                "supported_parameters": ["max_tokens", "temperature"],
            },
            {
                "provider_name": "NextBit",
                "pricing": {
                    "prompt": "0.00000009",
                    "completion": "0.0000003",
                    "input_cache_read": "0.00000005",
                },
                "supported_parameters": ["response_format", "structured_outputs"],
            },
        ]
    }
}


def test_i_prezzi_si_leggono_per_milione_di_token():
    endpoints = parse_endpoints(PAYLOAD)
    darkbloom = next(e for e in endpoints if e.provider == "Darkbloom")
    assert darkbloom.prompt == 0.042
    assert darkbloom.completion == 0.22
    assert darkbloom.cache_read is None
    assert darkbloom.structured is True

    nextbit = next(e for e in endpoints if e.provider == "NextBit")
    assert nextbit.cache_read == 0.05


def test_chi_non_regge_lo_schema_e_escluso_anche_se_costa_meno_del_secondo():
    """Il difetto che `require_parameters` previene, dimostrato sui numeri veri.

    DekaLLM a 0,060 è più economico di NextBit a 0,090, e senza il filtro finirebbe
    secondo in classifica — su un endpoint che non può rispettare `response_format`.
    """
    nomi = [e.provider for e in usable(parse_endpoints(PAYLOAD))]
    assert nomi == ["Darkbloom", "NextBit"]
    assert "DekaLLM" not in nomi


def test_il_lotto_unico_costa_meno_del_fan_out_sugli_stessi_termini():
    """Il calcolo che ha deciso la spec §12: il parallelo si sceglie per accuratezza.

    15 termini, prefisso di 3.100 token (anagrafica + prompt di sistema), 8 token di
    termine, 35 di risposta.
    """
    darkbloom = next(e for e in parse_endpoints(PAYLOAD) if e.provider == "Darkbloom")
    lotto = batch_cost(
        darkbloom, calls=1, prefix_tokens=3100, suffix_tokens=15 * 8, output_tokens=15 * 35
    )
    fan_out = batch_cost(
        darkbloom, calls=15, prefix_tokens=3100, suffix_tokens=8, output_tokens=35
    )
    assert lotto < fan_out
    # otto volte circa: l'ordine di grandezza è il dato che conta, non la cifra
    assert 5 < fan_out / lotto < 12


def test_un_endpoint_senza_cache_non_finge_di_averla():
    senza = Endpoint(
        provider="X", prompt=0.042, completion=0.22, cache_read=None, structured=True
    )
    con = Endpoint(
        provider="Y", prompt=0.042, completion=0.22, cache_read=0.01, structured=True
    )
    # a parità di tutto il resto, la cache può solo abbassare: se non c'è, il costo
    # resta quello del prezzo pieno, non zero e non un default inventato
    molte = dict(calls=10, prefix_tokens=1000, suffix_tokens=10, output_tokens=20)
    assert batch_cost(con, **molte) < batch_cost(senza, **molte)
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `docker compose exec backend pytest tests/test_llm_prices_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.cli.llm_prices'`.

- [ ] **Step 3: Scrivi `backend/app/cli/llm_prices.py`**

```python
"""I prezzi per provider del modello configurato, e il costo di un lotto vero.

Eseguire con `python -m app.cli.llm_prices` dentro il container del backend.

Non sta nel percorso caldo del riconoscimento, di proposito: l'instradamento vero lo
fa OpenRouter con `sort: "price"` e `require_parameters: true`, che è deterministico,
sempre aggiornato, e non costa una chiamata di rete in più a ogni import. Questo
comando serve a decidere se quel default va ancora bene — la documentazione di
OpenRouter non dichiara come `sort: "price"` pesi input contro output, e oggi la
lacuna non morde solo perché Darkbloom è il più economico su entrambe le voci. Il
giorno in cui qualcuno apre a 0,03 sull'input e 0,50 sull'output, il compromesso
esiste, e `OPENROUTER_PROVIDER_ONLY` è la leva.
"""

import asyncio
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

PER_MILLION = 1_000_000

# Il lotto di riferimento: misurati 169 ingredienti in anagrafica, 7,2 KB di JSON
# compatto, e col prompt di sistema un prefisso di ~3.100 token. Stimati 35 token di
# risposta per termine.
PREFIX_TOKENS = 3100
SUFFIX_TOKENS = 8
OUTPUT_TOKENS = 35
TERMS = 15
MAX_TERMS_PER_BATCH = 40


@dataclass(frozen=True)
class Endpoint:
    provider: str
    prompt: float       # dollari per milione di token
    completion: float
    cache_read: float | None
    structured: bool


def parse_endpoints(payload: dict) -> list[Endpoint]:
    """I prezzi di OpenRouter arrivano per token: qui diventano per milione.

    Per token sono numeri come 0.000000042, che non si confrontano a occhio e in cui
    uno zero in più o in meno non si vede. L'unità della tabella è quella con cui
    OpenRouter stessa scrive i listini.
    """
    endpoints = []
    for entry in payload.get("data", {}).get("endpoints", []):
        pricing = entry.get("pricing") or {}
        cache_read = pricing.get("input_cache_read")
        supported = entry.get("supported_parameters") or []
        endpoints.append(
            Endpoint(
                provider=str(entry.get("provider_name", "?")),
                prompt=float(pricing.get("prompt", 0)) * PER_MILLION,
                completion=float(pricing.get("completion", 0)) * PER_MILLION,
                cache_read=float(cache_read) * PER_MILLION if cache_read else None,
                structured="structured_outputs" in supported,
            )
        )
    return endpoints


def usable(endpoints: list[Endpoint]) -> list[Endpoint]:
    """Solo chi regge lo schema, dal più economico.

    È ciò che `require_parameters: true` fa lato OpenRouter, riprodotto qui: senza il
    filtro la classifica per prezzo include endpoint che non possono rispettare
    `response_format`, e il secondo posto è uno di quelli.
    """
    return sorted(
        (e for e in endpoints if e.structured), key=lambda e: (e.prompt, e.completion)
    )


def batch_cost(
    endpoint: Endpoint,
    *,
    calls: int,
    prefix_tokens: int,
    suffix_tokens: int,
    output_tokens: int,
) -> float:
    """Il costo in dollari di `calls` chiamate con quel prefisso e quella risposta.

    La prima chiamata paga il prefisso a prezzo pieno; le successive lo pagano a
    prezzo di cache read, se quel provider ne ha uno. Il suffisso — il termine da
    giudicare — è sempre a prezzo pieno.

    Su questo modello la cache non conviene mai, e il calcolo lo mostra invece di
    affermarlo: il cache read più economico fra i provider con structured output è
    0,050, più caro dei 0,042 che Darkbloom chiede per un token a prezzo pieno.
    """
    prefix_full = prefix_tokens * endpoint.prompt / PER_MILLION
    prefix_cached = (
        prefix_tokens * endpoint.cache_read / PER_MILLION
        if endpoint.cache_read is not None
        else prefix_full
    )
    suffix = suffix_tokens * endpoint.prompt / PER_MILLION
    output = output_tokens * endpoint.completion / PER_MILLION
    first = prefix_full + suffix + output
    rest = (calls - 1) * (prefix_cached + suffix + output)
    return first + rest


async def fetch_endpoints(client: httpx.AsyncClient) -> dict:
    settings = get_settings()
    url = f"{settings.openrouter_base_url.rstrip('/')}/models/{settings.openrouter_model}/endpoints"
    response = await client.get(url)
    response.raise_for_status()
    return response.json()


def render(endpoints: list[Endpoint]) -> str:
    righe = [f"{'PROVIDER':<14}{'INPUT':>8}{'OUTPUT':>9}{'CACHE R':>9}  SCHEMA"]
    for e in sorted(endpoints, key=lambda e: (e.prompt, e.completion)):
        cache = f"{e.cache_read:.3f}" if e.cache_read is not None else "—"
        schema = "sì" if e.structured else "NO"
        righe.append(f"{e.provider:<14}{e.prompt:>8.3f}{e.completion:>9.3f}{cache:>9}  {schema}")
    return "\n".join(righe)


async def main() -> None:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        payload = await fetch_endpoints(client)

    endpoints = parse_endpoints(payload)
    print(f"{settings.openrouter_model} — dollari per milione di token\n")
    print(render(endpoints))

    candidati = usable(endpoints)
    if not candidati:
        print(
            "\nNessun provider di questo modello supporta structured_outputs: con "
            "`require_parameters: true` ogni chiamata fallirebbe. Cambia OPENROUTER_MODEL."
        )
        return

    scelto = candidati[0]
    esclusi = [e.provider for e in endpoints if not e.structured]
    print(f"\nPiù economico fra quelli che reggono lo schema: {scelto.provider}")
    if esclusi:
        print(f"Esclusi perché senza structured_outputs: {', '.join(esclusi)}")

    lotti = -(-TERMS // MAX_TERMS_PER_BATCH)  # divisione per eccesso
    lotto_unico = batch_cost(
        scelto, calls=lotti, prefix_tokens=PREFIX_TOKENS,
        suffix_tokens=TERMS * SUFFIX_TOKENS, output_tokens=TERMS * OUTPUT_TOKENS,
    )
    fan_out = batch_cost(
        scelto, calls=TERMS, prefix_tokens=PREFIX_TOKENS,
        suffix_tokens=SUFFIX_TOKENS, output_tokens=OUTPUT_TOKENS,
    )
    print(f"\nSu {TERMS} termini, prefisso di {PREFIX_TOKENS} token:")
    print(f"  lotto unico            ${lotto_unico:.6f}")
    print(f"  una chiamata a termine ${fan_out:.6f}  ({fan_out / lotto_unico:.1f}×)")
    print(
        "\nIl fan-out si usa comunque: un modello con 3,8 miliardi di parametri attivi\n"
        "sbaglia un JSON di 40 elementi e non sbaglia una domanda sola (spec §4.2)."
    )


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Esegui il test e verifica che passi**

Run: `docker compose exec backend pytest tests/test_llm_prices_cli.py -v`
Expected: PASS, 4 test.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cli/llm_prices.py backend/tests/test_llm_prices_cli.py
git commit -m "feat: llm_prices, la tabella dei prezzi per provider e il costo di un lotto"
```

---

## Task 4: Alias e ingredienti, le tre operazioni condivise

`_remember_alias` vive oggi come funzione privata di `backend/app/api/imports.py`. Il riconoscimento automatico ha bisogno della stessa identica regola, e l'annullamento ha bisogno della sua inversa. Due copie della regola che decide cosa vale per sempre si scollerebbero, e la prima cosa a scollarsi sarebbe il vincolo su cui poggia l'autocomplete.

**Files:**
- Modify: `backend/app/repositories/ingredients.py`
- Modify: `backend/app/api/imports.py` (togli `_remember_alias`, chiama quella condivisa)
- Test: `backend/tests/db/test_ingredient_aliases.py`

**Interfaces:**
- Consumes: `add_alias(session, ingredient_id, alias, source)` già presente.
- Produces:
  - `async def remember_alias(session, ingredient_id: uuid.UUID, display_name: str) -> bool` — `True` se l'ha scritto
  - `async def forget_alias(session, ingredient_id: uuid.UUID, display_name: str) -> bool` — cancella solo il proprio, `source="import"`
  - `async def delete_ingredient_if_unused(session, ingredient_id: uuid.UUID) -> bool`

- [ ] **Step 1: Scrivi il test che fallisce**

In `backend/tests/db/test_ingredient_aliases.py`:

```python
"""Le tre operazioni su cui poggiano il riconoscimento automatico e il suo annullamento.

`remember_alias` è ciò che fa valere una decisione per sempre, e anche fuori
dall'import: l'autocomplete della lista della spesa legge gli stessi alias.
`forget_alias` e `delete_ingredient_if_unused` sono la sua inversa, e la loro
prudenza è il motivo per cui annullare non può fare danni.
"""

import pytest
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.recipe import RecipeSource
from app.repositories.ingredients import (
    add_alias,
    create_ingredient,
    delete_ingredient_if_unused,
    forget_alias,
    remember_alias,
)
from app.repositories.recipes import create_recipe


async def aliases(session, ingredient_id) -> list[str]:
    rows = await session.execute(
        select(IngredientAlias.alias).where(IngredientAlias.ingredient_id == ingredient_id)
    )
    return sorted(rows.scalars())


async def test_remember_alias_scrive_in_minuscolo_con_sorgente_import(db_session):
    pasta = await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    assert await remember_alias(db_session, pasta.id, "Rigatoni") is True
    assert await aliases(db_session, pasta.id) == ["rigatoni"]
    riga = (
        await db_session.execute(
            select(IngredientAlias).where(IngredientAlias.alias == "rigatoni")
        )
    ).scalar_one()
    assert riga.source == "import"


async def test_un_alias_gia_preso_da_un_altro_ingrediente_non_si_ruba(db_session):
    """Il vincolo del database è su `(ingredient_id, alias)`, non sull'alias.

    Lascerebbe passare lo stesso alias su due ingredienti diversi, cioè un
    autocomplete che dà due risposte a una domanda sola. Il legame fra termine e
    ingrediente vive su `import_terms`, quindi saltare la scrittura non perde niente.
    """
    pasta = await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    riso = await create_ingredient(
        db_session, name="riso", display_name="Riso", category=IngredientCategory.CEREALI
    )
    await add_alias(db_session, pasta.id, "rigatoni", source="import")

    assert await remember_alias(db_session, riso.id, "Rigatoni") is False
    assert await aliases(db_session, riso.id) == []


async def test_forget_alias_cancella_solo_il_proprio_e_solo_quelli_dellimport(db_session):
    pasta = await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    await add_alias(db_session, pasta.id, "rigatoni", source="import")
    await add_alias(db_session, pasta.id, "maccheroni", source="seed")

    assert await forget_alias(db_session, pasta.id, "Rigatoni") is True
    # un alias del seme non è nostro: annullare una decisione dell'AI non deve poter
    # smontare l'anagrafica di partenza
    assert await forget_alias(db_session, pasta.id, "Maccheroni") is False
    assert await aliases(db_session, pasta.id) == ["maccheroni"]


async def test_un_ingrediente_senza_usi_si_cancella(db_session):
    speck = await create_ingredient(
        db_session, name="speck", display_name="Speck", category=IngredientCategory.CARNE
    )
    assert await delete_ingredient_if_unused(db_session, speck.id) is True
    assert await db_session.get(Ingredient, speck.id) is None


async def test_un_ingrediente_usato_da_una_ricetta_resta(db_session):
    speck = await create_ingredient(
        db_session, name="speck", display_name="Speck", category=IngredientCategory.CARNE
    )
    await create_recipe(
        db_session, title="Pasta allo speck", description=None, instructions="cuoci",
        servings=2, source=RecipeSource.DATASET, source_ref=None,
        ingredients=[(speck.id, "primary", None, None)], embedding=None,
    )
    assert await delete_ingredient_if_unused(db_session, speck.id) is False
    assert await db_session.get(Ingredient, speck.id) is not None


async def test_un_ingrediente_in_dispensa_resta(db_session):
    speck = await create_ingredient(
        db_session, name="speck", display_name="Speck", category=IngredientCategory.CARNE
    )
    db_session.add(PantryItem(ingredient_id=speck.id, status="available"))
    await db_session.flush()
    assert await delete_ingredient_if_unused(db_session, speck.id) is False


async def test_i_suoi_alias_non_lo_trattengono(db_session):
    """Gli alias dell'import sono parte della decisione, non un uso indipendente.

    Se lo trattenessero, nessun ingrediente creato dall'AI sarebbe mai cancellabile:
    ogni decisione ne scrive uno.
    """
    speck = await create_ingredient(
        db_session, name="speck", display_name="Speck", category=IngredientCategory.CARNE
    )
    await add_alias(db_session, speck.id, "speck a cubetti", source="import")
    assert await delete_ingredient_if_unused(db_session, speck.id) is True
    assert await db_session.get(Ingredient, speck.id) is None
```

> Nota per chi implementa: controlla il nome del modello della dispensa prima di scrivere l'import. `grep -n "class PantryItem" -A6 backend/app/db/models/pantry.py` dice il modulo e i campi. Se il campo di stato non si chiama `status`, usa quello vero: il test va adattato al modello, non il modello al test.

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `docker compose exec backend pytest tests/db/test_ingredient_aliases.py -v`
Expected: FAIL — `ImportError: cannot import name 'remember_alias'`.

- [ ] **Step 3: Aggiungi le tre funzioni**

In fondo a `backend/app/repositories/ingredients.py`:

```python
async def remember_alias(
    session: AsyncSession, ingredient_id: uuid.UUID, display_name: str
) -> bool:
    """L'alias è ciò che fa valere una decisione per sempre, e anche fuori dall'import.

    Si scrive solo se quell'alias non esiste già per nessun ingrediente: il vincolo del
    database è su `(ingredient_id, alias)` e lascerebbe passare lo stesso alias su due
    ingredienti diversi, cioè un autocomplete che dà due risposte a una domanda sola.
    Il legame fra termine e ingrediente vive su `import_terms`, quindi saltarlo non
    perde la decisione.

    Torna `True` se l'ha scritto. Unica implementazione: la usano la decisione umana
    (api/imports.py), quella dell'AI (services/recipe_import/decide.py) e il collasso.
    Due copie di questa regola si scollerebbero, e la prima cosa a scollarsi sarebbe
    il vincolo su cui poggia l'autocomplete.
    """
    cleaned = display_name.strip().lower()
    if not cleaned:
        return False
    already = (
        await session.execute(select(IngredientAlias).where(IngredientAlias.alias == cleaned))
    ).scalars().first()
    if already is not None:
        return False
    await add_alias(session, ingredient_id, cleaned, source="import")
    return True


async def forget_alias(
    session: AsyncSession, ingredient_id: uuid.UUID, display_name: str
) -> bool:
    """L'inversa di `remember_alias`, e prudente per la stessa ragione.

    Cancella solo un alias scritto dall'import (`source="import"`) e solo su quel
    preciso ingrediente: annullare una decisione dell'AI non deve poter smontare
    l'anagrafica del seme, dove gli alias arrivano da `source="seed"` e valgono a
    prescindere da qualunque import.
    """
    cleaned = display_name.strip().lower()
    if not cleaned:
        return False
    entry = (
        await session.execute(
            select(IngredientAlias).where(
                IngredientAlias.ingredient_id == ingredient_id,
                IngredientAlias.alias == cleaned,
                IngredientAlias.source == "import",
            )
        )
    ).scalars().first()
    if entry is None:
        return False
    await session.delete(entry)
    await session.flush()
    return True


async def delete_ingredient_if_unused(
    session: AsyncSession, ingredient_id: uuid.UUID
) -> bool:
    """Cancella un ingrediente solo se nessuno lo usa più. Torna `True` se l'ha fatto.

    «Usarlo» significa: una riga di ricetta, un articolo in dispensa, una voce di
    lista, o un termine dell'import che lo indica. I suoi **alias** non contano: sono
    parte della decisione che lo ha creato, non un uso indipendente, e se contassero
    nessun ingrediente creato dall'AI sarebbe mai cancellabile — ogni decisione ne
    scrive uno.

    È questo controllo che rende gratuito l'annullamento di un collasso: se «salmone
    selvaggio» era stato accorpato in «salmone», annullare «Salmone» trova l'altro
    termine e non cancella niente.
    """
    from app.db.models.pantry import PantryItem
    from app.db.models.recipe import RecipeIngredient
    from app.db.models.recipe_import import ImportTerm

    for model, column in (
        (RecipeIngredient, RecipeIngredient.ingredient_id),
        (PantryItem, PantryItem.ingredient_id),
        (ShoppingListItem, ShoppingListItem.ingredient_id),
        (ImportTerm, ImportTerm.ingredient_id),
    ):
        used = (
            await session.execute(select(model.id).where(column == ingredient_id).limit(1))
        ).scalars().first()
        if used is not None:
            return False

    await session.execute(
        delete(IngredientAlias).where(IngredientAlias.ingredient_id == ingredient_id)
    )
    ingredient = await session.get(Ingredient, ingredient_id)
    if ingredient is None:
        return False
    await session.delete(ingredient)
    await session.flush()
    return True
```

Aggiungi `delete` all'import di `sqlalchemy` in cima al file: `from sqlalchemy import case, delete, func, select`.

- [ ] **Step 4: Esegui il test e verifica che passi**

Run: `docker compose exec backend pytest tests/db/test_ingredient_aliases.py -v`
Expected: PASS, 7 test.

- [ ] **Step 5: Togli la copia privata da `api/imports.py`**

Cancella la funzione `_remember_alias` in fondo al file, aggiungi `remember_alias` all'import da `app.repositories.ingredients`, e nella rotta `decide` sostituisci `await _remember_alias(session, ingredient.id, term.display_name)` con `await remember_alias(session, ingredient.id, term.display_name)`.

- [ ] **Step 6: Verifica che la suite dell'import non sia cambiata di comportamento**

Run: `docker compose exec backend pytest tests/api/test_imports.py tests/db/test_ingredient_aliases.py -v`
Expected: PASS. Se un test sugli alias dell'import falliva prima di questo passaggio, la funzione condivisa non è equivalente a quella privata: confronta le due, non toccare il test.

- [ ] **Step 7: Commit**

```bash
git add backend/app/repositories/ingredients.py backend/app/api/imports.py backend/tests/db/test_ingredient_aliases.py
git commit -m "refactor: alias e cancellazione dell'ingrediente in un posto solo"
```

---

## Task 5: Una decisione per termine

**Files:**
- Create: `backend/app/services/recipe_import/decide.py`
- Test: `backend/tests/services/test_decide_one.py`

**Interfaces:**
- Consumes: `complete_json`, `open_client`, `LlmUnavailable` (Task 2); `match_name` da `app.services.ingredient_match`.
- Produces:
  - `TERM_SYSTEM_PROMPT: str`, `TERM_SCHEMA: dict`, `TERM_MAX_TOKENS: int`
  - `@dataclass(frozen=True) class Registry` con `by_name: dict[str, uuid.UUID]`, `name_by_id: dict[uuid.UUID, str]`, `entries: list[tuple[str, str]]`
  - `async def load_registry(session) -> Registry`
  - `@dataclass(frozen=True) class TermDecisionProposal` con `term_id: uuid.UUID`, `action: str`, `ingredient_id: uuid.UUID | None`, `name: str | None`, `display_name: str | None`, `category: str | None`
  - `async def decide_one(session, term: ImportTerm, registry: Registry, client=None) -> TermDecisionProposal | None`

- [ ] **Step 0: Crea `backend/tests/llm_fakes.py`**

Con il contenuto della sezione «Preliminare» qui sopra. Cinque task lo usano; scriverlo
adesso evita che ognuno si faccia il suo.

- [ ] **Step 1: Scrivi il test che fallisce**

In `backend/tests/services/test_decide_one.py`:

```python
"""Una domanda sola al modello, e la verifica della sua risposta.

La verifica è la parte che conta: da qui passa la differenza fra «il modello può
sbagliare» e «il modello può scrivere spazzatura». Una risposta non verificabile non
diventa una proposta — torna `None`, e il termine resta in coda.
"""

import json

import pytest
import pytest_asyncio

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.repositories.ingredients import create_ingredient
from app.services.llm import LlmUnavailable
from app.services.recipe_import.decide import decide_one, load_registry
from llm_fakes import FakeLlm


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def anagrafica(db_session):
    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    return await load_registry(db_session)


def termine(nome: str, chiave: str) -> ImportTerm:
    return ImportTerm(
        source=GIALLOZAFFERANO, term_key=chiave, display_name=nome,
        occurrences=3, decision=TermDecision.PENDING,
    )


async def test_map_verso_un_ingrediente_esistente(db_session, anagrafica):
    term = termine("Rigatoni", "ricette-con-i-Rigatoni")
    db_session.add(term)
    await db_session.flush()

    finto = FakeLlm({"action": "map", "ingredient": "pasta", "name": None,
                     "display_name": None, "category": None})
    proposta = await decide_one(db_session, term, anagrafica, client=finto)

    assert proposta is not None
    assert proposta.action == "map"
    assert proposta.ingredient_id == anagrafica.by_name["pasta"]
    # il nome canonico viaggia con la proposta: è la sola fonte di un testo leggibile
    # che la revisione può mostrare senza fidarsi di un id cieco
    assert proposta.name == "pasta"


async def test_create_con_categoria_valida(db_session, anagrafica):
    term = termine("Speck", "ricette-con-lo-Speck")
    db_session.add(term)
    await db_session.flush()

    finto = FakeLlm({"action": "create", "ingredient": None, "name": "speck",
                     "display_name": "Speck", "category": "carne"})
    proposta = await decide_one(db_session, term, anagrafica, client=finto)

    assert proposta is not None
    assert (proposta.action, proposta.name, proposta.category) == ("create", "speck", "carne")


async def test_ignore(db_session, anagrafica):
    term = termine("Acqua", "ricette-con-Acqua")
    db_session.add(term)
    await db_session.flush()

    finto = FakeLlm({"action": "ignore", "ingredient": None, "name": None,
                     "display_name": None, "category": None})
    proposta = await decide_one(db_session, term, anagrafica, client=finto)
    assert proposta is not None and proposta.action == "ignore"


async def test_un_map_verso_un_ingrediente_inesistente_non_e_una_proposta(db_session, anagrafica):
    term = termine("Rigatoni", "ricette-con-i-Rigatoni")
    db_session.add(term)
    await db_session.flush()

    finto = FakeLlm({"action": "map", "ingredient": "pasta integrale di kamut",
                     "name": None, "display_name": None, "category": None})
    assert await decide_one(db_session, term, anagrafica, client=finto) is None


async def test_una_categoria_inventata_non_e_una_proposta(db_session, anagrafica):
    term = termine("Speck", "ricette-con-lo-Speck")
    db_session.add(term)
    await db_session.flush()

    finto = FakeLlm({"action": "create", "ingredient": None, "name": "speck",
                     "display_name": "Speck", "category": "salumi"})
    assert await decide_one(db_session, term, anagrafica, client=finto) is None


async def test_un_create_di_un_nome_che_esiste_diventa_un_map(db_session, anagrafica):
    """Lo stesso caso che per `map` si scarterebbe, e qui si converte.

    Un `create` di «pasta» non si può applicare: il 409 lo rifiuterebbe a ogni tocco.
    Ma l'ingrediente esiste, quindi la carta verificata non è il `create` sbagliato: è
    il `map` che il modello avrebbe dovuto scegliere, e id e nome li abbiamo già dalla
    stessa ricerca che verifica un `map` vero.
    """
    term = termine("Rigatoni", "ricette-con-i-Rigatoni")
    db_session.add(term)
    await db_session.flush()

    finto = FakeLlm({"action": "create", "ingredient": None, "name": "pasta",
                     "display_name": "Pasta", "category": "cereali"})
    proposta = await decide_one(db_session, term, anagrafica, client=finto)

    assert proposta is not None
    assert proposta.action == "map"
    assert proposta.ingredient_id == anagrafica.by_name["pasta"]


async def test_unazione_sconosciuta_non_e_una_proposta(db_session, anagrafica):
    term = termine("Speck", "ricette-con-lo-Speck")
    db_session.add(term)
    await db_session.flush()

    finto = FakeLlm({"action": "forse", "ingredient": None, "name": None,
                     "display_name": None, "category": None})
    assert await decide_one(db_session, term, anagrafica, client=finto) is None


async def test_un_guasto_del_modello_risale(db_session, anagrafica):
    """`decide_one` non inghiotte `LlmUnavailable`: chi orchestra decide cosa farne.

    Il fan-out la cattura per termine (un guasto lascia in coda solo il suo termine);
    il CLI la cattura per il lotto. Inghiottirla qui renderebbe indistinguibile «il
    modello è giù» da «il modello ha risposto una cosa inutilizzabile».
    """
    term = termine("Speck", "ricette-con-lo-Speck")
    db_session.add(term)
    await db_session.flush()

    import httpx

    finto = FakeLlm(httpx.ReadTimeout("lento"))
    with pytest.raises(LlmUnavailable):
        await decide_one(db_session, term, anagrafica, client=finto)


async def test_la_domanda_porta_il_termine_lanagrafica_e_le_categorie(db_session, anagrafica):
    term = termine("Rigatoni", "ricette-con-i-Rigatoni")
    db_session.add(term)
    await db_session.flush()

    finto = FakeLlm({"action": "ignore", "ingredient": None, "name": None,
                     "display_name": None, "category": None})
    await decide_one(db_session, term, anagrafica, client=finto)

    corpo = finto.bodies[0]
    domanda = json.loads(corpo["messages"][1]["content"])
    assert domanda["termine"] == "Rigatoni"
    assert {"nome": "pasta", "categoria": "cereali"} in domanda["anagrafica"]
    assert "carne" in domanda["categorie"]
    # una domanda sola, non un array: è la scelta di §4.2 della spec
    assert isinstance(domanda["termine"], str)
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `docker compose exec backend pytest tests/services/test_decide_one.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.recipe_import.decide'`.

- [ ] **Step 3: Scrivi la prima metà di `decide.py`**

```python
"""Il riconoscimento degli ingredienti sconosciuti, con un LLM che decide.

Quattro passi, e l'ordine di esecuzione non è quello in cui si leggono qui:

1. il filtro deterministico sta in `terms.py`, in `sync_terms`: un termine che
   coincide con un nostro nome o alias si decide da sé, senza chiamare nessuno. Solo
   ciò che resta `pending` arriva qui;
2. **fan-out** — `decide_one` per ogni termine, in parallelo, senza scrivere;
3. **collasso** — una chiamata sola sui soli `create`, senza scrivere;
4. **fan-in** — le scritture, in sequenza.

Una chiamata per termine e non un lotto unico: `gemma-4-26b-a4b-it` ha 3,8 miliardi
di parametri attivi per token, e un array JSON di 40 elementi ognuno dei quali deve
riecheggiare identica una delle 40 stringhe ricevute è dove un MoE piccolo si sfalda.
Il degrado sarebbe invisibile — gli elementi non riconosciuti si scartano in silenzio
— e costerebbe un ottavo. Vedi spec §4.2 e §12: il parallelo si paga in soldi e si
guadagna in accuratezza.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe_import import ImportTerm
from app.services.llm import LlmUnavailable, complete_json, open_client

TERM_MAX_TOKENS = 300  # una decisione sola: qui sopra c'è solo spazio per divagare

TERM_SYSTEM_PROMPT = """Sei un aiuto per mettere in ordine un'anagrafica di ingredienti. Ricevi UN nome di ingrediente preso da un sito di cucina, e l'anagrafica di un'app di dispensa. Scegli UNA delle tre azioni.

- "map": è lo stesso ingrediente di uno che esiste già in anagrafica, scritto più in dettaglio. "Rigatoni" è pasta, "Latte intero" è latte. Metti in "ingredient" il nome canonico esistente, scritto identico.
- "create": è un ingrediente generico che l'anagrafica non ha. Metti in "name" il nome canonico in italiano minuscolo e singolare, in "display_name" il nome da mostrare, in "category" una delle categorie che ti passo, scritta identica.
- "ignore": non è qualcosa che si tiene in dispensa. L'acqua, il ghiaccio, l'acqua per la cottura.

Regole:
- Preferisci "map" quando l'ingrediente esiste già: un'anagrafica con venti formati di pasta non sa più dire cosa c'è in casa.
- I campi che non servono all'azione scelta valgono null.
- Non inserire valori nutrizionali, calorie o macronutrienti.
"""

TERM_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["map", "create", "ignore"]},
        "ingredient": {"type": ["string", "null"]},
        "name": {"type": ["string", "null"]},
        "display_name": {"type": ["string", "null"]},
        "category": {"type": ["string", "null"]},
    },
    # Vincolo dello strict mode: ogni proprietà in `required`, additionalProperties a
    # false. È il motivo per cui i campi di una sola azione sono nullable e non
    # opzionali — dichiararli opzionali farebbe rifiutare lo schema.
    "required": ["action", "ingredient", "name", "display_name", "category"],
    "additionalProperties": False,
}

CATEGORIES = frozenset(str(value) for value in IngredientCategory)


@dataclass(frozen=True)
class Registry:
    """L'anagrafica in una forma che sta in un prompt e si interroga senza database.

    Si carica una volta per lotto e non una per termine: con N chiamate in parallelo
    sarebbero N letture identiche della stessa tabella.
    """

    by_name: dict[str, uuid.UUID]
    name_by_id: dict[uuid.UUID, str]
    entries: list[tuple[str, str]]  # (nome, categoria), ordinati per nome


async def load_registry(session: AsyncSession) -> Registry:
    rows = list(
        (
            await session.execute(
                select(Ingredient.id, Ingredient.name, Ingredient.category).order_by(
                    Ingredient.name
                )
            )
        ).all()
    )
    return Registry(
        by_name={name: ingredient_id for ingredient_id, name, _ in rows},
        name_by_id={ingredient_id: name for ingredient_id, name, _ in rows},
        entries=[(name, category) for _, name, category in rows],
    )


@dataclass(frozen=True)
class TermDecisionProposal:
    term_id: uuid.UUID
    action: str
    ingredient_id: uuid.UUID | None = None
    name: str | None = None
    display_name: str | None = None
    category: str | None = None


def _question(term: ImportTerm, registry: Registry) -> str:
    return json.dumps(
        {
            "termine": term.display_name,
            "anagrafica": [{"nome": name, "categoria": category} for name, category in registry.entries],
            "categorie": sorted(CATEGORIES),
        },
        ensure_ascii=False,
    )


async def decide_one(
    session: AsyncSession,
    term: ImportTerm,
    registry: Registry,
    client: object | None = None,
) -> TermDecisionProposal | None:
    """Una decisione verificata per questo termine, o `None` se non è verificabile.

    `None` non è un guasto: è «il modello ha risposto qualcosa che non posso
    applicare», e il termine resta in coda. `LlmUnavailable` invece risale: chi
    orchestra deve poter distinguere «il modello è giù» da «il modello ha detto una
    cosa inutilizzabile», perché la prima si ritenta e la seconda no.

    `session` non serve oggi alla verifica — il registro basta — ed è nella firma
    perché il chiamante ce l'ha già e perché il collasso e l'applicazione la vogliono:
    una firma diversa per ognuno dei tre passi renderebbe il fan-out più difficile da
    leggere di quanto valga.
    """
    payload = await complete_json(
        system=TERM_SYSTEM_PROMPT,
        user=_question(term, registry),
        schema=TERM_SCHEMA,
        schema_name="decisione_termine",
        max_tokens=TERM_MAX_TOKENS,
        client=client,
    )

    action = payload.get("action")

    if action == "ignore":
        return TermDecisionProposal(term_id=term.id, action="ignore")

    if action == "map":
        name = str(payload.get("ingredient") or "").strip().lower()
        ingredient_id = registry.by_name.get(name)
        if ingredient_id is None:
            return None  # un ingrediente che non esiste non è una proposta
        return TermDecisionProposal(
            term_id=term.id, action="map", ingredient_id=ingredient_id,
            name=registry.name_by_id.get(ingredient_id),
        )

    if action == "create":
        name = str(payload.get("name") or "").strip().lower()
        category = str(payload.get("category") or "").strip().lower()
        if not name or category not in CATEGORIES:
            return None
        existing = registry.by_name.get(name)
        if existing is not None:
            # Un `create` di un nome che l'anagrafica ha già: il 409 lo rifiuterebbe a
            # ogni tentativo. Ma la carta verificata non è il `create` sbagliato, è il
            # `map` che il modello avrebbe dovuto scegliere — e id e nome canonico li
            # abbiamo già, dalla stessa ricerca che verifica un `map` vero.
            return TermDecisionProposal(
                term_id=term.id, action="map", ingredient_id=existing,
                name=registry.name_by_id.get(existing),
            )
        return TermDecisionProposal(
            term_id=term.id, action="create", name=name,
            display_name=str(payload.get("display_name") or name).strip(),
            category=category,
        )

    return None  # un'azione che non conosco
```

- [ ] **Step 4: Esegui il test e verifica che passi**

Run: `docker compose exec backend pytest tests/services/test_decide_one.py -v`
Expected: PASS, 9 test.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/recipe_import/decide.py backend/tests/services/test_decide_one.py
git commit -m "feat: una decisione per termine, verificata contro l'anagrafica vera"
```

---

## Task 6: La passata di collasso

**Files:**
- Modify: `backend/app/services/recipe_import/decide.py`
- Test: `backend/tests/services/test_collapse.py`

**Interfaces:**
- Consumes: `TermDecisionProposal`, `Registry`, `load_registry` (Task 5); `search_ingredients` da `app.repositories.ingredients`.
- Produces:
  - `COLLAPSE_SYSTEM_PROMPT: str`, `COLLAPSE_SCHEMA: dict`, `COLLAPSE_MAX_TOKENS: int`
  - `async def collapse_creates(session, proposals: list[TermDecisionProposal], registry: Registry, client=None) -> list[TermDecisionProposal]`

- [ ] **Step 1: Scrivi il test che fallisce**

In `backend/tests/services/test_collapse.py`:

```python
"""Il collasso dei nomi vicini, che è il buco che il parallelo apre.

Il fan-in prende i duplicati identici («speck» due volte). Non vede i vicini:
«salmone» e «salmone selvaggio» sono due `create` diversi, e nessuna delle chiamate
parallele poteva vedere l'altra. Questa passata li unisce, e il nome scartato diventa
un alias del canonico — che è ciò che la rende un investimento e non una pulizia: la
prossima volta il filtro deterministico lo riconosce senza chiamare nessuno.
"""

import uuid

import pytest
import pytest_asyncio

from app.db.models.ingredient import IngredientCategory
from app.repositories.ingredients import create_ingredient
from app.services.recipe_import.decide import (
    TermDecisionProposal,
    collapse_creates,
    load_registry,
)
from llm_fakes import FakeLlm


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def anagrafica(db_session):
    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    return await load_registry(db_session)


def crea(nome: str, categoria: str = "pesce") -> TermDecisionProposal:
    return TermDecisionProposal(
        term_id=uuid.uuid4(), action="create", name=nome,
        display_name=nome.capitalize(), category=categoria,
    )


async def test_due_nomi_vicini_diventano_uno_e_laltro_un_alias(db_session, anagrafica):
    salmone, selvaggio = crea("salmone"), crea("salmone selvaggio")
    finto = FakeLlm({"groups": [{"canonical": "salmone", "merge": ["salmone selvaggio"]}]})

    risultato = await collapse_creates(
        db_session, [salmone, selvaggio], anagrafica, client=finto
    )

    creazioni = [p for p in risultato if p.action == "create"]
    assert [p.name for p in creazioni] == ["salmone"]
    # il secondo non spariste: resta una proposta, e chiede di essere agganciato al
    # canonico. L'alias lo scrive il fan-in, non questa passata: qui non si scrive.
    accorpati = [p for p in risultato if p.action == "merge"]
    assert len(accorpati) == 1
    assert accorpati[0].term_id == selvaggio.term_id
    assert accorpati[0].name == "salmone"


async def test_un_canonico_che_nessuno_ha_proposto_fa_scartare_il_gruppo(db_session, anagrafica):
    """La direzione del fallimento è quella giusta.

    Scartare un collasso lascia un ingrediente in più — si vede e si corregge.
    Applicarne uno sbagliato lascia una distinzione in meno, ed è invisibile.
    """
    salmone, selvaggio = crea("salmone"), crea("salmone selvaggio")
    finto = FakeLlm({"groups": [{"canonical": "pesce", "merge": ["salmone", "salmone selvaggio"]}]})

    risultato = await collapse_creates(
        db_session, [salmone, selvaggio], anagrafica, client=finto
    )
    assert sorted(p.name for p in risultato if p.action == "create") == [
        "salmone", "salmone selvaggio"
    ]
    assert not [p for p in risultato if p.action == "merge"]


async def test_un_nome_da_accorpare_che_nessuno_ha_proposto_si_ignora(db_session, anagrafica):
    salmone = crea("salmone")
    finto = FakeLlm({"groups": [{"canonical": "salmone", "merge": ["tonno"]}]})

    risultato = await collapse_creates(db_session, [salmone], anagrafica, client=finto)
    assert [p.name for p in risultato if p.action == "create"] == ["salmone"]
    assert not [p for p in risultato if p.action == "merge"]


async def test_un_canonico_che_esiste_gia_in_anagrafica_e_valido(db_session, anagrafica):
    """Nuovo contro esistente: il caso che la chiamata singola avrebbe dovuto prendere.

    «Pasta fresca» proposto come `create` mentre «pasta» esiste: qui si recupera, e
    diventa un aggancio all'ingrediente vero invece di un quindicesimo cereale.
    """
    fresca = crea("pasta fresca", categoria="cereali")
    finto = FakeLlm({"groups": [{"canonical": "pasta", "merge": ["pasta fresca"]}]})

    risultato = await collapse_creates(db_session, [fresca], anagrafica, client=finto)
    assert not [p for p in risultato if p.action == "create"]
    accorpato = next(p for p in risultato if p.action == "merge")
    assert accorpato.ingredient_id == anagrafica.by_name["pasta"]
    assert accorpato.name == "pasta"


async def test_senza_create_non_si_chiama_nessuno(db_session, anagrafica):
    """Zero costo nel caso comune: un lotto di soli `map` non fa nessuna domanda."""
    solo_map = TermDecisionProposal(
        term_id=uuid.uuid4(), action="map",
        ingredient_id=anagrafica.by_name["pasta"], name="pasta",
    )
    finto = FakeLlm()
    risultato = await collapse_creates(db_session, [solo_map], anagrafica, client=finto)
    assert risultato == [solo_map]
    assert finto.bodies == []


async def test_un_solo_create_non_si_chiama_nessuno(db_session, anagrafica):
    """Un nome solo non ha nessuno con cui collassare fra i nuovi.

    Il confronto con l'anagrafica esistente lo ha già fatto `decide_one`, con tutta
    l'anagrafica nel prompt: rifarlo qui su un nome solo è una chiamata che non può
    scoprire niente di nuovo.
    """
    finto = FakeLlm()
    risultato = await collapse_creates(db_session, [crea("speck", "carne")], anagrafica, client=finto)
    assert [p.name for p in risultato] == ["speck"]
    assert finto.bodies == []


async def test_un_guasto_del_modello_non_perde_le_proposte(db_session, anagrafica):
    """Il collasso è un miglioramento, non un requisito: se cade, si applica il resto.

    Far fallire tutto il lotto perché la passata di rifinitura non ha risposto
    significherebbe buscare N decisioni buone per una chiamata in meno.
    """
    import httpx

    salmone, selvaggio = crea("salmone"), crea("salmone selvaggio")
    finto = FakeLlm(httpx.ReadTimeout("lento"))

    risultato = await collapse_creates(
        db_session, [salmone, selvaggio], anagrafica, client=finto
    )
    assert sorted(p.name for p in risultato if p.action == "create") == [
        "salmone", "salmone selvaggio"
    ]
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `docker compose exec backend pytest tests/services/test_collapse.py -v`
Expected: FAIL — `ImportError: cannot import name 'collapse_creates'`.

- [ ] **Step 3: Aggiungi il collasso a `decide.py`**

Nota: l'azione `"merge"` è interna a questo modulo. Il fan-in la traduce in un `map` all'ingrediente canonico più un alias sul nome scartato; non arriva mai al database come azione.

```python
COLLAPSE_MAX_TOKENS = 800

COLLAPSE_SYSTEM_PROMPT = """Sei un aiuto per mettere in ordine un'anagrafica di ingredienti di un'app di dispensa, che serve a rispondere «ce l'ho in casa?».

Ricevi una lista di nomi di ingredienti che stanno per essere aggiunti, e per ognuno i nomi già presenti in anagrafica che gli assomigliano. Raggruppa i nomi che sono lo stesso ingrediente.

Per ogni gruppo:
- "canonical": il nome che sopravvive. Deve essere uno dei nomi che ti passo — fra quelli nuovi o fra quelli già in anagrafica. Non inventarne uno terzo.
- "merge": i nomi nuovi che diventano varianti di quel canonico. Solo nomi presenti nella lista che ti ho dato.

Regole:
- Raggruppa solo ciò che in cucina è la stessa cosa. "Salmone" e "Salmone selvaggio" sì. "Cipolla" e "Cipollotto" NO: sono ingredienti diversi.
- Nel dubbio non raggruppare: due ingredienti in più si correggono, una distinzione perduta no.
- Se non c'è niente da raggruppare, torna una lista vuota.
- Non inserire valori nutrizionali.
"""

COLLAPSE_SCHEMA = {
    "type": "object",
    "properties": {
        "groups": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "canonical": {"type": "string"},
                    "merge": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["canonical", "merge"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["groups"],
    "additionalProperties": False,
}

NEIGHBOURS_PER_NAME = 3


async def collapse_creates(
    session: AsyncSession,
    proposals: list[TermDecisionProposal],
    registry: Registry,
    client: object | None = None,
) -> list[TermDecisionProposal]:
    """Unisce i `create` che sono lo stesso ingrediente. Non scrive niente.

    Copre due rischi in una chiamata: nuovo contro nuovo (che nessuna delle chiamate
    parallele poteva vedere) e nuovo contro esistente (che `decide_one` avrebbe dovuto
    prendere, e che un modello con 3,8 miliardi di parametri attivi a volte non
    prende).

    I vicini si trovano con `search_ingredients`, la ricerca per trigrammi che è già
    la primitiva di somiglianza del progetto: al modello arriva un input minuscolo e
    non l'anagrafica intera.

    Zero chiamate quando non c'è niente da chiedere: nessun `create`, o uno solo — un
    nome solo non ha nessuno con cui collassare fra i nuovi, e il confronto con
    l'anagrafica l'ha già fatto `decide_one` con tutta l'anagrafica nel prompt.

    Un guasto del modello non perde il lotto: si tornano le proposte come sono
    arrivate. Il collasso è una rifinitura, e far cadere N decisioni buone per una
    chiamata andata male sarebbe il contrario di quel che serve.
    """
    from app.repositories.ingredients import search_ingredients

    creates = [p for p in proposals if p.action == "create" and p.name]
    if len(creates) < 2:
        return list(proposals)

    proposed = {p.name: p for p in creates if p.name}
    neighbours: dict[str, list[str]] = {}
    for name in proposed:
        found = await search_ingredients(session, name, limit=NEIGHBOURS_PER_NAME)
        neighbours[name] = [ingredient.name for ingredient in found]

    question = json.dumps(
        {
            "nuovi": [
                {"nome": name, "simili_in_anagrafica": neighbours[name]} for name in proposed
            ]
        },
        ensure_ascii=False,
    )

    try:
        payload = await complete_json(
            system=COLLAPSE_SYSTEM_PROMPT,
            user=question,
            schema=COLLAPSE_SCHEMA,
            schema_name="collasso_ingredienti",
            max_tokens=COLLAPSE_MAX_TOKENS,
            client=client,
        )
    except LlmUnavailable:
        return list(proposals)

    groups = payload.get("groups")
    if not isinstance(groups, list):
        return list(proposals)

    merged: dict[str, TermDecisionProposal] = {}
    for group in groups:
        if not isinstance(group, dict):
            continue
        canonical = str(group.get("canonical") or "").strip().lower()
        names = group.get("merge")
        if not canonical or not isinstance(names, list):
            continue

        # il canonico deve essere qualcosa che esiste o che stiamo creando: un terzo
        # nome inventato fa scartare il gruppo, e i nomi restano separati
        existing_id = registry.by_name.get(canonical)
        if canonical not in proposed and existing_id is None:
            continue

        for raw in names:
            name = str(raw or "").strip().lower()
            if name == canonical or name not in proposed:
                continue  # un nome che nessuno ha proposto non si accorpa
            losing = proposed[name]
            winner = proposed.get(canonical)
            merged[name] = TermDecisionProposal(
                term_id=losing.term_id,
                action="merge",
                ingredient_id=existing_id,  # None quando il canonico è un `create` del lotto
                name=canonical,
                # Nome visibile e categoria sono quelli del **vincitore**, non del nome
                # che perde. Quando il canonico è un `create` dello stesso lotto, il
                # fan-in può trovarsi a creare l'ingrediente partendo da questa
                # proposta — dipende da quale delle due incontra prima — e con
                # l'etichetta del perdente nascerebbe «salmone» con nome visibile
                # «Salmone selvaggio». Prenderli dal vincitore rende il risultato
                # indipendente dall'ordine, che è la sola forma in cui è corretto.
                display_name=(
                    winner.display_name if winner is not None else canonical.capitalize()
                ),
                category=winner.category if winner is not None else losing.category,
            )

    out: list[TermDecisionProposal] = []
    for proposal in proposals:
        replacement = merged.get(proposal.name) if proposal.action == "create" else None
        out.append(replacement if replacement is not None else proposal)
    return out
```

- [ ] **Step 4: Esegui il test e verifica che passi**

Run: `docker compose exec backend pytest tests/services/test_collapse.py -v`
Expected: PASS, 7 test.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/recipe_import/decide.py backend/tests/services/test_collapse.py
git commit -m "feat: la passata di collasso, che unisce i nomi vicini prima di scriverli"
```

---

## Task 7: Fan-out, fan-in, e le scritture

**Files:**
- Modify: `backend/app/services/recipe_import/decide.py`
- Test: `backend/tests/services/test_decide_terms.py`

**Interfaces:**
- Consumes: `decide_one`, `collapse_creates`, `load_registry` (Task 5, 6); `remember_alias`, `create_ingredient` (Task 4); `match_name`.
- Produces:
  - `@dataclass(frozen=True) class Decided` con `applied: int`, `created: int`, `ignored: int`, `still_pending: int`
  - `async def decide_terms(session, terms: list[ImportTerm], client=None) -> Decided`

- [ ] **Step 1: Scrivi il test che fallisce**

In `backend/tests/services/test_decide_terms.py`:

```python
"""Il fan-out, il fan-in, e la proprietà che il parallelo mette a rischio.

Il test che conta più di tutti è `test_due_create_dello_stesso_nome...`: è il buco che
si apre passando da un lotto unico a N chiamate parallele, e la sua chiusura — le
scritture in sequenza, con `match_name` rifatto prima di ogni `create` — è la ragione
per cui il fan-in esiste.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.repositories.ingredients import create_ingredient
from app.services.recipe_import.decide import decide_terms
from llm_fakes import LLM_IGNORE, ScriptedLlm, llm_create, llm_map


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def base(db_session):
    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )


def termine(nome: str, chiave: str, quante: int = 3) -> ImportTerm:
    return ImportTerm(
        source=GIALLOZAFFERANO, term_key=chiave, display_name=nome,
        occurrences=quante, decision=TermDecision.PENDING,
    )


async def aggiungi(db_session, *termini: ImportTerm) -> list[ImportTerm]:
    db_session.add_all(termini)
    await db_session.flush()
    return list(termini)


async def test_le_tre_azioni_si_applicano(db_session, base):
    rigatoni, speck, acqua = await aggiungi(
        db_session,
        termine("Rigatoni", "k-rigatoni"),
        termine("Speck", "k-speck"),
        termine("Acqua", "k-acqua"),
    )
    finto = ScriptedLlm({
        "Rigatoni": llm_map("pasta"),
        "Speck": llm_create("speck", "Speck", "carne"),
        "Acqua": LLM_IGNORE,
    })

    esito = await decide_terms(db_session, [rigatoni, speck, acqua], client=finto)

    assert esito.applied == 3
    assert esito.created == 1
    assert esito.ignored == 1
    assert esito.still_pending == 0

    assert rigatoni.decision == TermDecision.MAPPED
    assert rigatoni.decided_by == "ai"
    assert rigatoni.decided_at is not None
    assert speck.decision == TermDecision.MAPPED
    assert acqua.decision == TermDecision.IGNORED
    assert acqua.ingredient_id is None

    creato = await db_session.get(Ingredient, speck.ingredient_id)
    assert (creato.name, creato.display_name, creato.category) == ("speck", "Speck", "carne")


async def test_ogni_decisione_scrive_lalias_permanente(db_session, base):
    (rigatoni,) = await aggiungi(db_session, termine("Rigatoni", "k-rigatoni"))
    finto = ScriptedLlm({"Rigatoni": llm_map("pasta")})

    await decide_terms(db_session, [rigatoni], client=finto)

    alias = (
        await db_session.execute(
            select(IngredientAlias).where(IngredientAlias.alias == "rigatoni")
        )
    ).scalar_one()
    assert alias.ingredient_id == rigatoni.ingredient_id
    assert alias.source == "import"


async def test_un_termine_ignorato_non_scrive_nessun_alias(db_session, base):
    """Un alias su un termine ignorato non punterebbe a niente, e resterebbe."""
    (acqua,) = await aggiungi(db_session, termine("Acqua", "k-acqua"))
    await decide_terms(db_session, [acqua], client=ScriptedLlm({"Acqua": LLM_IGNORE}))

    trovati = (
        await db_session.execute(
            select(IngredientAlias).where(IngredientAlias.alias == "acqua")
        )
    ).scalars().all()
    assert trovati == []


async def test_due_create_dello_stesso_nome_fanno_un_ingrediente_e_due_termini(db_session, base):
    """Il buco che il parallelo apre, e la sua chiusura.

    Scritte in parallelo, queste due proposte sarebbero un doppione o una violazione
    del vincolo di unicità. Applicate in sequenza con `match_name` rifatto prima di
    ogni `create`, la seconda trova quello che la prima ha appena creato.
    """
    speck, cubetti = await aggiungi(
        db_session, termine("Speck", "k-speck"), termine("Speck a cubetti", "k-speck-cubetti")
    )
    finto = ScriptedLlm({
        "Speck": llm_create("speck", "Speck", "carne"),
        "Speck a cubetti": llm_create("speck", "Speck a cubetti", "carne"),
    })

    esito = await decide_terms(db_session, [speck, cubetti], client=finto)

    assert esito.created == 1
    assert speck.ingredient_id == cubetti.ingredient_id
    quanti = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "speck"))
    ).scalars().all()
    assert len(quanti) == 1
    # entrambi i termini portano il loro alias, che è ciò che li farà riconoscere
    # senza chiamare nessuno al prossimo giro
    alias = (
        await db_session.execute(
            select(IngredientAlias.alias).where(
                IngredientAlias.ingredient_id == speck.ingredient_id
            )
        )
    ).scalars().all()
    assert sorted(alias) == ["speck", "speck a cubetti"]


async def test_un_collasso_produce_un_ingrediente_e_due_termini(db_session, base):
    salmone, selvaggio = await aggiungi(
        db_session, termine("Salmone", "k-salmone"), termine("Salmone selvaggio", "k-salmone-s")
    )
    finto = ScriptedLlm(
        {
            "Salmone": llm_create("salmone", "Salmone", "pesce"),
            "Salmone selvaggio": llm_create("salmone selvaggio", "Salmone selvaggio", "pesce"),
        },
        collapse={"groups": [{"canonical": "salmone", "merge": ["salmone selvaggio"]}]},
    )

    esito = await decide_terms(db_session, [salmone, selvaggio], client=finto)

    assert esito.created == 1
    assert salmone.ingredient_id == selvaggio.ingredient_id
    nomi = (
        await db_session.execute(select(Ingredient.name).where(Ingredient.category == "pesce"))
    ).scalars().all()
    assert nomi == ["salmone"]
    # il nome perdente non si butta: diventa l'alias che lo farà riconoscere da solo
    alias = (
        await db_session.execute(
            select(IngredientAlias.alias).where(
                IngredientAlias.ingredient_id == salmone.ingredient_id
            )
        )
    ).scalars().all()
    assert "salmone selvaggio" in alias


async def test_una_risposta_non_verificabile_lascia_il_termine_in_coda(db_session, base):
    rigatoni, speck = await aggiungi(
        db_session, termine("Rigatoni", "k-rigatoni"), termine("Speck", "k-speck")
    )
    finto = ScriptedLlm({
        "Rigatoni": llm_map("pasta"),
        "Speck": llm_create("speck", "Speck", "salumi"),  # categoria inventata
    })

    esito = await decide_terms(db_session, [rigatoni, speck], client=finto)

    assert esito.applied == 1
    assert esito.still_pending == 1
    assert rigatoni.decision == TermDecision.MAPPED
    assert speck.decision == TermDecision.PENDING
    assert speck.decided_by is None


async def test_un_guasto_su_un_termine_non_tocca_gli_altri(db_session, base):
    """L'isolamento del guasto, che è l'altro regalo del fan-out.

    Con un lotto unico una chiamata caduta perdeva tutte le decisioni del lotto.
    """
    import httpx

    rigatoni, speck = await aggiungi(
        db_session, termine("Rigatoni", "k-rigatoni"), termine("Speck", "k-speck")
    )
    finto = ScriptedLlm({
        "Rigatoni": llm_map("pasta"),
        "Speck": httpx.ReadTimeout("lento"),
    })

    esito = await decide_terms(db_session, [rigatoni, speck], client=finto)

    assert esito.applied == 1
    assert esito.still_pending == 1
    assert rigatoni.decision == TermDecision.MAPPED
    assert speck.decision == TermDecision.PENDING


async def test_una_lista_vuota_non_chiama_nessuno(db_session, base):
    finto = ScriptedLlm({})
    esito = await decide_terms(db_session, [], client=finto)
    assert esito == type(esito)(applied=0, created=0, ignored=0, still_pending=0)
    assert finto.calls == 0


async def test_senza_chiave_solleva_invece_di_decidere_a_caso(db_session, base, monkeypatch):
    from app.core.config import get_settings
    from app.services.llm import LlmUnavailable

    (rigatoni,) = await aggiungi(db_session, termine("Rigatoni", "k-rigatoni"))
    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    try:
        with pytest.raises(LlmUnavailable):
            await decide_terms(db_session, [rigatoni])
    finally:
        get_settings.cache_clear()
    assert rigatoni.decision == TermDecision.PENDING
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `docker compose exec backend pytest tests/services/test_decide_terms.py -v`
Expected: FAIL — `ImportError: cannot import name 'decide_terms'`.

- [ ] **Step 3: Aggiungi il fan-out e il fan-in a `decide.py`**

```python
@dataclass(frozen=True)
class Decided:
    applied: int
    created: int
    ignored: int
    still_pending: int


async def decide_terms(
    session: AsyncSession, terms: list[ImportTerm], client: object | None = None
) -> Decided:
    """Decide i termini in attesa e applica: fan-out, collasso, fan-in.

    Le domande partono insieme sotto un semaforo (`LLM_MAX_CONCURRENCY`); le
    **scritture** si applicano dopo, in sequenza e in ordine, rifacendo `match_name`
    prima di ogni `create`. Il parallelo è sulla rete, non sul database: due `create`
    dello stesso nome scritti insieme sarebbero un doppione o una violazione del
    vincolo, e in sequenza il secondo trova quello che il primo ha appena creato.

    Un guasto su un termine lascia in coda solo quel termine. `LlmUnavailable`
    risale solo quando **nessuna** chiamata è partita — manca la chiave — perché
    quello non è un intoppo: è una configurazione assente, e chi chiama la traduce in
    «decidi a mano».
    """
    from app.repositories.ingredients import create_ingredient, remember_alias
    from app.services.ingredient_match import match_name

    if not terms:
        return Decided(applied=0, created=0, ignored=0, still_pending=0)

    # senza chiave si esce prima di aprire qualunque cosa: è la configurazione, non
    # un intoppo, e N fallimenti identici non sono più informativi di uno
    build_headers()

    registry = await load_registry(session)
    semaphore = asyncio.Semaphore(get_settings().llm_max_concurrency)

    async def ask(term: ImportTerm, api: object) -> TermDecisionProposal | None:
        async with semaphore:
            try:
                return await decide_one(session, term, registry, client=api)
            except LlmUnavailable:
                # questo termine resta in coda; gli altri non ne sanno niente
                return None

    owned = client is None
    api = client if client is not None else open_client()
    try:
        raw = await asyncio.gather(*(ask(term, api) for term in terms))
        proposals = [p for p in raw if p is not None]
        proposals = await collapse_creates(session, proposals, registry, client=api)
    finally:
        if owned:
            await api.aclose()

    by_id = {term.id: term for term in terms}
    applied = created = ignored = 0

    for proposal in proposals:
        term = by_id.get(proposal.term_id)
        if term is None:
            continue

        if proposal.action == "ignore":
            term.decision = TermDecision.IGNORED
            term.ingredient_id = None
            # nessun alias: punterebbe a niente, e resterebbe
            ignored += 1
        else:
            # `merge` e `map` chiedono entrambi un ingrediente esistente; `create` lo
            # fa nascere. `match_name` si rifà qui e non si fida del registro caricato
            # in cima: le scritture di questo stesso giro lo hanno già superato.
            ingredient_id = proposal.ingredient_id
            if ingredient_id is None and proposal.name:
                match = await match_name(session, proposal.name)
                if match.certain:
                    ingredient_id = match.ingredient_id
            if ingredient_id is None:
                if proposal.action not in ("create", "merge") or not proposal.name:
                    continue
                ingredient = await create_ingredient(
                    session,
                    name=proposal.name,
                    display_name=proposal.display_name or proposal.name,
                    category=proposal.category or "altro",
                )
                ingredient_id = ingredient.id
                created += 1

            term.decision = TermDecision.MAPPED
            term.ingredient_id = ingredient_id
            await remember_alias(session, ingredient_id, term.display_name)

        term.decided_by = "ai"
        term.decided_at = datetime.now(UTC)
        applied += 1

    await session.flush()
    still_pending = sum(1 for term in terms if term.decision == TermDecision.PENDING)
    return Decided(
        applied=applied, created=created, ignored=ignored, still_pending=still_pending
    )
```

Aggiungi in cima a `decide.py`: `from datetime import UTC, datetime`, `from app.db.models.recipe_import import TermDecision` accanto a `ImportTerm`, e `build_headers` all'import da `app.services.llm`.

> Nota su un caso sottile del collasso: quando il canonico di un gruppo è un `create` dello stesso lotto, la proposta `merge` arriva con `ingredient_id=None` e `name` uguale al nome canonico. Il fan-in la risolve con `match_name` se il canonico è già stato creato in questa passata, e altrimenti lo crea lei — che è il comportamento giusto a prescindere dall'ordine in cui le due proposte si trovano nella lista. Il test `test_un_collasso_produce_un_ingrediente_e_due_termini` copre esattamente questo.

- [ ] **Step 4: Esegui il test e verifica che passi**

Run: `docker compose exec backend pytest tests/services/test_decide_terms.py -v`
Expected: PASS, 9 test.

- [ ] **Step 5: Togli `propose_decisions` da `terms.py`**

Cancella da `backend/app/services/recipe_import/terms.py` tutto ciò che riguarda le proposte: `PROPOSAL_MODEL`, `PROPOSAL_MAX_TOKENS`, `MAX_TERMS_PER_CALL`, `PROPOSAL_SYSTEM_PROMPT`, `TermProposal`, `propose_decisions`, e gli import di `AiUnavailable`, `_build_client`, `Ingredient`, `IngredientCategory`, `json`, `uuid`, `dataclass` che restano senza uso. `sync_terms` e `TermsSynced` restano identici. Cancella anche `backend/tests/services/test_term_proposals.py`, che provava la funzione appena rimossa.

- [ ] **Step 6: Verifica che niente si sia rotto**

Run: `docker compose exec backend pytest tests/services -v`
Expected: PASS. Se qualcosa importa ancora `propose_decisions`, l'errore lo dice: quel punto di chiamata è l'`api/imports.py` del Task 9, che si sistema lì. Se il Task 9 non è ancora fatto, tieni il punto di chiamata rotto **solo** finché la suite dei servizi passa e sistemalo subito dopo — non lasciare il repository con un import rotto attraverso un commit.

Per evitarlo del tutto: fai questo Step 5 e il Task 9 nello stesso commit, oppure porta avanti il Task 9 prima dello Step 5.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/recipe_import/decide.py backend/app/services/recipe_import/terms.py backend/tests/services/test_decide_terms.py
git rm backend/tests/services/test_term_proposals.py
git commit -m "feat: decide_terms applica le decisioni dell'AI, in parallelo e scrivendo in ordine"
```

---

## Task 8: Lo scarico decide da sé

**Files:**
- Modify: `backend/app/cli/import_gz.py`
- Test: `backend/tests/test_import_gz_cli.py` (aggiungi; non riscrivere i test esistenti)

**Interfaces:**
- Consumes: `decide_terms`, `Decided` (Task 7); `LlmUnavailable` (Task 2).
- Produces: `run_import` guadagna il parametro `llm_client: object | None = None` e, in `ImportRun`, i campi `decided: int` e `still_pending: int`.

- [ ] **Step 1: Scrivi il test che fallisce**

Aggiungi a `backend/tests/test_import_gz_cli.py`:

```python
async def test_lo_scarico_decide_i_termini_e_materializza(db_session, monkeypatch):
    """Un comando solo: scarica, decide, e le ricette entrano.

    È il criterio di riuscita numero 1 della spec. Prima di questo cambiamento il
    comando finiva su «0 importate, 5 in attesa» e aspettava una persona.
    """
    from app.core.config import get_settings
    from app.db.models.recipe import Recipe
    from app.cli.import_gz import run_import
    from llm_fakes import ScriptedLlm, llm_create, llm_map

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    try:
        # usa lo stesso apparato dei test esistenti di questo file per la fonte finta:
        # cerca la fixture o l'helper che serve la sitemap e le pagine, e riusala.
        # Il punto nuovo di questo test è solo `llm_client`.
        client = fonte_finta_con_una_ricetta()  # vedi gli altri test di questo file
        llm = ScriptedLlm(
            {"Rigatoni": llm_map("pasta"), "Speck": llm_create("speck", "Speck", "carne")}
        )

        esito = await run_import(
            db_session, limit=1, client=client, sleep=nessuna_pausa, llm_client=llm
        )

        assert esito.taken == 1
        assert esito.decided >= 1
        ricette = (await db_session.execute(select(Recipe))).scalars().all()
        assert len(ricette) == 1
    finally:
        get_settings.cache_clear()


async def test_senza_chiave_lo_scarico_non_fallisce_e_lascia_i_termini_in_coda(
    db_session, monkeypatch
):
    """La degradazione dichiarata: mai un vicolo cieco.

    Senza chiave il comando deve comportarsi come prima di questa feature — pagine
    salvate, termini in coda, uscita pulita — non morire su un'eccezione.
    """
    from app.core.config import get_settings
    from app.cli.import_gz import run_import
    from app.db.models.recipe_import import ImportTerm, TermDecision

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    try:
        client = fonte_finta_con_una_ricetta()
        esito = await run_import(db_session, limit=1, client=client, sleep=nessuna_pausa)

        assert esito.taken == 1
        assert esito.decided == 0
        in_coda = (
            await db_session.execute(
                select(ImportTerm).where(ImportTerm.decision == TermDecision.PENDING)
            )
        ).scalars().all()
        assert in_coda != []
    finally:
        get_settings.cache_clear()
```

> Nota per chi implementa: `fonte_finta_con_una_ricetta()` e `nessuna_pausa` non esistono con questi nomi. Leggi `backend/tests/test_import_gz_cli.py` e riusa l'apparato che è già lì per la sitemap e le pagine finte, con i suoi nomi veri. Se quell'apparato è una fixture, chiedila come parametro. Non introdurre un secondo modo di fingere la fonte: due modi si scollano, e questo file è già quello che la fonte finta la sa fare.

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `docker compose exec backend pytest tests/test_import_gz_cli.py -v`
Expected: FAIL — `run_import() got an unexpected keyword argument 'llm_client'`.

- [ ] **Step 3: Modifica `import_gz.py`**

`ImportRun` diventa:

```python
@dataclass(frozen=True)
class ImportRun:
    taken: int
    skipped: int
    stopped_early: bool
    decided: int = 0
    still_pending: int = 0
```

`run_import` prende `llm_client: object | None = None` fra i parametri con nome, e le ultime righe diventano:

```python
    # i termini si allineano sempre, anche dopo un giro fermato a metà: le pagine
    # prese devono comparire in coda, altrimenti il lavoro fatto non si vede
    await sync_terms(session, GIALLOZAFFERANO)

    # Poi l'AI decide quel che sa decidere, e solo allora si materializza: in
    # quest'ordine un comando solo riempie il ricettario. Senza chiave configurata
    # `LlmUnavailable` arriva qui e non oltre — le pagine restano salvate, i termini in
    # coda, e il comando esce pulito. È la regola «mai un vicolo cieco».
    decided = 0
    still_pending = 0
    waiting = await pending_terms(session, GIALLOZAFFERANO, limit=MAX_TERMS_PER_RUN)
    if waiting:
        try:
            outcome = await decide_terms(session, waiting, client=llm_client)
            decided = outcome.applied
            still_pending = outcome.still_pending
        except LlmUnavailable as exc:
            still_pending = len(waiting)
            print(f"riconoscimento non disponibile ({exc}): i termini restano in coda.")

    await materialize_ready(session, GIALLOZAFFERANO)
    return ImportRun(
        taken=taken, skipped=skipped, stopped_early=stopped_early,
        decided=decided, still_pending=still_pending,
    )
```

Import nuovi in cima:

```python
from app.repositories.imports import counts, known_urls, pending_terms, store_page, store_unparsable
from app.services.llm import LlmUnavailable
from app.services.recipe_import.decide import decide_terms
```

E accanto a `DEFAULT_LIMIT`:

```python
# Quanti termini l'AI giudica in un giro. Una chiamata a termine: il tetto è
# sull'attesa e sulla spesa di un singolo lancio, non sulla correttezza — i termini
# che restano fuori li prende il lancio successivo, o il bottone «Riprova con l'AI».
MAX_TERMS_PER_RUN = 60
```

In `main()`, dopo la riga del ricettario, aggiungi:

```python
    if result.decided:
        print(f"{result.decided} ingredienti riconosciuti da sé")
```

e cambia la riga finale dei termini in attesa così che dica dove si rivedono:

```python
    if totals.pending_terms:
        print(
            f"{totals.pending_terms} ingredienti da abbinare a mano: aprili dal "
            "ricettario, alla riga in cima. Le ricette entrano da sé mentre decidi."
        )
```

- [ ] **Step 4: Esegui i test e verifica che passino**

Run: `docker compose exec backend pytest tests/test_import_gz_cli.py -v`
Expected: PASS, tutti — compresi quelli che c'erano prima, che non devono essere stati modificati.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cli/import_gz.py backend/tests/test_import_gz_cli.py
git commit -m "feat: lo scarico riconosce gli ingredienti da sé e materializza"
```

---

## Task 9: `POST /imports/terms/decide` al posto di `/terms/proposals`

Stessa funzione, verbo onesto: applica invece di proporre. Serve come «riprova con l'AI» sui termini rimasti in coda dopo un guasto di rete.

**Files:**
- Modify: `backend/app/api/imports.py`
- Modify: `backend/app/schemas/recipe_import.py`
- Test: `backend/tests/api/test_imports_decide.py`

**Interfaces:**
- Consumes: `decide_terms`, `Decided` (Task 7).
- Produces:
  - schemi: `DecideRequest` con `term_ids: list[uuid.UUID] | None = None`; `DecideOut` con `applied: int`, `created: int`, `ignored: int`, `still_pending: int`, `unlocked: int`, `remaining_terms: int`
  - rotta: `POST /api/v1/imports/terms/decide`
  - rimossi: `ProposalsRequest`, `ProposalOut`, `ProposalsOut`, e la rotta `POST /terms/proposals`

- [ ] **Step 1: Scrivi il test che fallisce**

In `backend/tests/api/test_imports_decide.py`:

```python
"""La rotta che fa decidere all'AI i termini rimasti in coda.

Non torna proposte da confermare: applica, e dice quante ricette ha sbloccato. È la
differenza fra la coda di prima — un modulo da compilare — e quella di adesso, che è
la revisione di un lavoro già fatto.
"""

import pytest
from sqlalchemy import select

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.repositories.ingredients import create_ingredient
from llm_fakes import ScriptedLlm, llm_map


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


async def test_la_rotta_applica_e_dice_cosa_resta(client, db_session, monkeypatch):
    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-rigatoni", display_name="Rigatoni",
        occurrences=3, decision=TermDecision.PENDING,
    )
    db_session.add(term)
    await db_session.flush()

    # il client finto si inietta sostituendo la funzione che apre quello vero: la
    # rotta non ha un parametro per passarlo, e non deve averlo — un parametro
    # iniettabile da HTTP sarebbe una via per far parlare il backend con un endpoint
    # scelto da chi chiama
    import app.services.recipe_import.decide as modulo

    monkeypatch.setattr(
        modulo, "open_client", lambda: ScriptedLlm({"Rigatoni": llm_map("pasta")})
    )

    response = await client.post("/api/v1/imports/terms/decide", json={})
    assert response.status_code == 200
    corpo = response.json()
    assert corpo["applied"] == 1
    assert corpo["still_pending"] == 0
    assert corpo["remaining_terms"] == 0

    await db_session.refresh(term)
    assert term.decision == TermDecision.MAPPED
    assert term.decided_by == "ai"


async def test_senza_chiave_risponde_503_e_dice_che_la_coda_funziona(
    client, db_session, monkeypatch
):
    from app.core.config import get_settings

    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-speck", display_name="Speck",
        occurrences=1, decision=TermDecision.PENDING,
    )
    db_session.add(term)
    await db_session.flush()

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    try:
        response = await client.post("/api/v1/imports/terms/decide", json={})
        assert response.status_code == 503
        assert "a mano" in response.json()["detail"]
    finally:
        get_settings.cache_clear()

    await db_session.refresh(term)
    assert term.decision == TermDecision.PENDING


async def test_senza_termini_in_coda_non_e_un_errore(client):
    """Una coda vuota è il caso migliore, non un 404: la schermata non deve allarmare."""
    response = await client.post("/api/v1/imports/terms/decide", json={})
    assert response.status_code == 200
    assert response.json()["applied"] == 0


async def test_term_ids_restringe_a_quei_termini(client, db_session, monkeypatch):
    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    uno = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-rigatoni", display_name="Rigatoni",
        occurrences=3, decision=TermDecision.PENDING,
    )
    due = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-penne", display_name="Penne",
        occurrences=2, decision=TermDecision.PENDING,
    )
    db_session.add_all([uno, due])
    await db_session.flush()

    import app.services.recipe_import.decide as modulo

    monkeypatch.setattr(
        modulo, "open_client", lambda: ScriptedLlm({"Rigatoni": llm_map("pasta")})
    )

    response = await client.post(
        "/api/v1/imports/terms/decide", json={"term_ids": [str(uno.id)]}
    )
    assert response.status_code == 200
    await db_session.refresh(due)
    assert due.decision == TermDecision.PENDING


async def test_la_vecchia_rotta_delle_proposte_non_esiste_piu(client):
    """Una rotta morta che risponde 200 è peggio di una che non c'è.

    Il frontend non la chiama più; lasciarla in piedi significherebbe mantenere due
    modi di decidere, e uno dei due non sarebbe mai esercitato.
    """
    response = await client.post(
        "/api/v1/imports/terms/proposals", json={"term_ids": []}
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `docker compose exec backend pytest tests/api/test_imports_decide.py -v`
Expected: FAIL — 404 sulla rotta `/terms/decide`.

- [ ] **Step 3: Cambia gli schemi**

In `backend/app/schemas/recipe_import.py` cancella `ProposalsRequest`, `ProposalOut`, `ProposalsOut` e aggiungi:

```python
class DecideRequest(BaseModel):
    """`term_ids` assente significa «tutti quelli in coda».

    È il caso normale: il bottone della schermata non ha una selezione da mandare, e
    obbligarlo a costruirla lo farebbe sbagliare appena la coda si accorcia sotto di
    lui. La lista esiste per chi vuole insistere su un termine preciso.
    """

    term_ids: list[uuid.UUID] | None = Field(default=None, max_length=200)


class DecideOut(BaseModel):
    applied: int
    created: int
    ignored: int
    still_pending: int
    # le ricette entrate grazie a queste decisioni: è il numero che rende il
    # riconoscimento un lavoro con un risultato visibile
    unlocked: int
    remaining_terms: int
```

- [ ] **Step 4: Cambia la rotta**

In `backend/app/api/imports.py` sostituisci per intero la rotta `read_proposals` con:

```python
@router.post("/terms/decide", response_model=DecideOut)
async def decide_with_ai(
    payload: DecideRequest, session: AsyncSession = Depends(get_session)
) -> DecideOut:
    """Fa decidere all'AI i termini in coda, e applica.

    Non torna proposte da confermare: le decisioni si applicano, con `decided_by="ai"`,
    e si rivedono dall'elenco «Deciso dall'AI» con un annullamento per ognuna. Un
    termine la cui risposta non passa la verifica resta in coda, e la coda manuale è
    identica a prima.
    """
    if payload.term_ids:
        rows = await session.execute(
            select(ImportTerm).where(
                ImportTerm.id.in_(payload.term_ids),
                ImportTerm.decision == TermDecision.PENDING,
            )
        )
        terms = list(rows.scalars())
    else:
        terms = await pending_terms(session, GIALLOZAFFERANO, limit=MAX_TERMS_PER_CALL)

    try:
        outcome = await decide_terms(session, terms)
    except LlmUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"il riconoscimento non è disponibile ({exc}): decidi a mano, la coda funziona.",
        ) from exc

    materialized = await materialize_ready(session, GIALLOZAFFERANO)
    numbers = await counts(session, GIALLOZAFFERANO)
    await session.commit()
    return DecideOut(
        applied=outcome.applied, created=outcome.created, ignored=outcome.ignored,
        still_pending=outcome.still_pending, unlocked=materialized.created,
        remaining_terms=numbers.pending_terms,
    )
```

Aggiusta gli import in cima al file: togli `AiUnavailable` e `propose_decisions`, aggiungi

```python
from app.services.llm import LlmUnavailable
from app.services.recipe_import.decide import decide_terms
```

e negli schemi importa `DecideOut`, `DecideRequest` al posto di `ProposalOut`, `ProposalsOut`, `ProposalsRequest`. Definisci accanto al router:

```python
# Quanti termini in un giro della rotta. Una chiamata a termine: il tetto è
# sull'attesa di chi ha premuto il bottone, non sulla correttezza.
MAX_TERMS_PER_CALL = 40
```

Aggiungi `TermDecision` all'import da `app.db.models.recipe_import` se non c'è già.

- [ ] **Step 5: Esegui il test e verifica che passi**

Run: `docker compose exec backend pytest tests/api/test_imports_decide.py tests/api/test_imports.py -v`
Expected: PASS. Se qualche test di `test_imports.py` provava `/terms/proposals`, cancella quei test: la rotta non c'è più, e la funzione che provavano è coperta da `test_decide_terms.py`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/imports.py backend/app/schemas/recipe_import.py backend/tests/api/test_imports_decide.py backend/tests/api/test_imports.py
git commit -m "feat: POST /imports/terms/decide applica, e /terms/proposals esce"
```

---

## Task 10: Annullare una decisione

**Files:**
- Create: `backend/app/services/recipe_import/undo.py`
- Modify: `backend/app/api/imports.py`
- Modify: `backend/app/schemas/recipe_import.py`
- Test: `backend/tests/services/test_undo.py`, `backend/tests/api/test_imports_undo.py`

**Interfaces:**
- Consumes: `forget_alias`, `delete_ingredient_if_unused` (Task 4).
- Produces:
  - `@dataclass(frozen=True) class Undone` con `recipes_requeued: int`, `ingredient_deleted: bool`, `alias_forgotten: bool`
  - `class CookedRecipesAffected(Exception)` con attributo `count: int`
  - `async def undo_decision(session, term: ImportTerm, *, force: bool = False) -> Undone`
  - schemi: `UndoRequest` con `force: bool = False`; `UndoOut` con `recipes_requeued: int`, `ingredient_deleted: bool`, `remaining_terms: int`
  - rotta: `POST /api/v1/imports/terms/{term_id}/undo`

- [ ] **Step 1: Scrivi il test del servizio**

In `backend/tests/services/test_undo.py`:

```python
"""Annullare una decisione: rimettere il mondo come era, e non un editor.

Un verbo solo. Dopo l'annullamento il termine è in coda e si decide a mano con la
scheda che esiste già ed è già testata — niente secondo percorso di decisione da
scrivere e mantenere.

Le ricette si rifanno da `payload`, che è ancora nel database esattamente per questo
(spec madre §6.1): non serve nessuna chirurgia su `recipe_ingredients`.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.recipe import CookingEvent, Recipe, RecipeSource
from app.db.models.recipe_import import (
    GIALLOZAFFERANO,
    ImportState,
    ImportTerm,
    RecipeImport,
    TermDecision,
)
from app.repositories.ingredients import create_ingredient, remember_alias
from app.repositories.recipes import create_recipe
from app.services.recipe_import.undo import CookedRecipesAffected, undo_decision


@pytest_asyncio.fixture
async def deciso(db_session):
    """Un termine deciso dall'AI, con l'ingrediente creato, l'alias e la ricetta."""
    speck = await create_ingredient(
        db_session, name="speck", display_name="Speck", category=IngredientCategory.CARNE
    )
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-speck", display_name="Speck",
        occurrences=1, decision=TermDecision.MAPPED, ingredient_id=speck.id,
        decided_by="ai",
    )
    db_session.add(term)
    await db_session.flush()
    await remember_alias(db_session, speck.id, "Speck")

    recipe = await create_recipe(
        db_session, title="Pasta allo speck", description=None, instructions="cuoci",
        servings=2, source=RecipeSource.DATASET, source_ref="https://esempio.invalid/1",
        ingredients=[(speck.id, "primary", "100 g", None)], embedding=None,
    )
    page = RecipeImport(
        source=GIALLOZAFFERANO, url="https://esempio.invalid/1",
        payload={"title": "Pasta allo speck", "ingredients": [{"key": "k-speck", "name": "Speck"}]},
        state=ImportState.IMPORTED, recipe_id=recipe.id,
    )
    db_session.add(page)
    await db_session.flush()
    return term, speck, recipe, page


async def test_il_termine_torna_in_coda_pulito(db_session, deciso):
    term, _, _, _ = deciso
    await undo_decision(db_session, term)
    assert term.decision == TermDecision.PENDING
    assert term.ingredient_id is None
    assert term.decided_by is None
    assert term.decided_at is None
    assert term.role_override is None


async def test_lalias_scritto_dalla_decisione_si_cancella(db_session, deciso):
    term, speck, _, _ = deciso
    await undo_decision(db_session, term)
    trovati = (
        await db_session.execute(
            select(IngredientAlias).where(IngredientAlias.alias == "speck")
        )
    ).scalars().all()
    assert trovati == []


async def test_lingrediente_creato_e_non_piu_usato_si_cancella(db_session, deciso):
    term, speck, _, _ = deciso
    esito = await undo_decision(db_session, term)
    assert esito.ingredient_deleted is True
    assert await db_session.get(Ingredient, speck.id) is None


async def test_la_ricetta_torna_in_coda_e_la_pagina_torna_pending(db_session, deciso):
    term, _, recipe, page = deciso
    esito = await undo_decision(db_session, term)

    assert esito.recipes_requeued == 1
    assert await db_session.get(Recipe, recipe.id) is None
    await db_session.refresh(page)
    assert page.state == ImportState.PENDING
    assert page.recipe_id is None


async def test_un_ingrediente_che_un_altro_termine_usa_resta(db_session, deciso):
    """È questo controllo che rende gratuito l'annullamento di un collasso.

    Se «Speck a cubetti» era stato accorpato sullo stesso ingrediente, annullare
    «Speck» trova l'altro termine e non cancella niente.
    """
    term, speck, _, _ = deciso
    altro = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-speck-cubetti", display_name="Speck a cubetti",
        occurrences=1, decision=TermDecision.MAPPED, ingredient_id=speck.id, decided_by="ai",
    )
    db_session.add(altro)
    await db_session.flush()

    esito = await undo_decision(db_session, term)
    assert esito.ingredient_deleted is False
    assert await db_session.get(Ingredient, speck.id) is not None


async def test_una_ricetta_gia_cucinata_blocca_finche_non_si_insiste(db_session, deciso):
    """L'unico punto di tutta la feature in cui si chiede qualcosa.

    `cooking_events.recipe_id` è ON DELETE SET NULL: lo storico sopravvive col suo
    snapshot, ma perde il collegamento alla ricetta, per sempre. Quello storico esiste
    solo perché la fase 3 e la fase 4 ci costruiscono sopra. Rifiutare in silenzio
    sarebbe un vicolo cieco, procedere in silenzio una perdita invisibile.
    """
    term, _, recipe, _ = deciso
    db_session.add(CookingEvent(recipe_id=recipe.id, servings=2, snapshot={}))
    await db_session.flush()

    with pytest.raises(CookedRecipesAffected) as errore:
        await undo_decision(db_session, term)
    assert errore.value.count == 1

    # niente è stato toccato: un'eccezione a metà lavoro sarebbe peggio del rifiuto
    assert term.decision == TermDecision.MAPPED
    assert await db_session.get(Recipe, recipe.id) is not None


async def test_con_force_si_procede_e_lo_storico_resta_orfano(db_session, deciso):
    term, _, recipe, _ = deciso
    evento = CookingEvent(recipe_id=recipe.id, servings=2, snapshot={"titolo": "Pasta allo speck"})
    db_session.add(evento)
    await db_session.flush()

    esito = await undo_decision(db_session, term, force=True)

    assert esito.recipes_requeued == 1
    assert await db_session.get(Recipe, recipe.id) is None
    await db_session.refresh(evento)
    assert evento.recipe_id is None
    # lo snapshot è ciò che sopravvive, ed è il motivo per cui questo è accettabile
    assert evento.snapshot == {"titolo": "Pasta allo speck"}


async def test_annullare_un_termine_ignorato_funziona(db_session):
    """Un `ignore` non ha ingrediente né alias: l'annullamento deve reggerlo comunque."""
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-acqua", display_name="Acqua",
        occurrences=2, decision=TermDecision.IGNORED, ingredient_id=None, decided_by="ai",
    )
    db_session.add(term)
    await db_session.flush()

    esito = await undo_decision(db_session, term)
    assert term.decision == TermDecision.PENDING
    assert esito.ingredient_deleted is False
    assert esito.alias_forgotten is False


async def test_una_pagina_cancellata_dallutente_non_si_resuscita(db_session, deciso):
    """`state='imported'` con `recipe_id` nullo è una cancellazione dell'utente.

    La regola del modello — «è lo stato, non la presenza della chiave, a dire già
    importata una volta» — dice che quella pagina non deve tornare. Rimetterla a
    `pending` la farebbe ricreare, e la cancellazione non sarebbe mai definitiva.
    """
    term, _, recipe, page = deciso
    await db_session.delete(recipe)
    await db_session.flush()
    await db_session.refresh(page)
    assert page.state == ImportState.IMPORTED and page.recipe_id is None

    esito = await undo_decision(db_session, term)
    assert esito.recipes_requeued == 0
    await db_session.refresh(page)
    assert page.state == ImportState.IMPORTED
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `docker compose exec backend pytest tests/services/test_undo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.recipe_import.undo'`.

- [ ] **Step 3: Scrivi `backend/app/services/recipe_import/undo.py`**

```python
"""Disfare una decisione: il termine, l'alias, l'ingrediente, le pagine.

Un verbo solo, e non un editor delle decisioni. Dopo l'annullamento il termine è
esattamente dov'era prima che l'AI lo toccasse, e si decide a mano con la scheda che
esiste già ed è già testata: niente secondo percorso di decisione da scrivere e
mantenere.

Le ricette non si correggono, si rifanno. `recipe_imports.payload` è ancora nel
database esattamente per questo (spec madre §6.1), quindi rimettere la pagina a
`pending` e lasciare che `materialize_ready` la ricostruisca è più corretto di
qualunque chirurgia su `recipe_ingredients` — e non può sbagliare a metà.

Non c'è niente da preservare nelle ricette cancellate: l'applicazione non ha rotte per
modificare o cancellare una ricetta. Il giorno in cui esisterà una modifica a mano,
questo file va ripensato.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.recipe import CookingEvent, Recipe
from app.db.models.recipe_import import ImportState, ImportTerm, RecipeImport, TermDecision
from app.repositories.ingredients import delete_ingredient_if_unused, forget_alias


@dataclass(frozen=True)
class Undone:
    recipes_requeued: int
    ingredient_deleted: bool
    alias_forgotten: bool


class CookedRecipesAffected(Exception):
    """Fra le ricette da rifare ce n'è almeno una già cucinata.

    Non è un guasto: è una conseguenza che va detta prima, perché `cooking_events`
    perderebbe il collegamento alla ricetta per sempre. Con `force=True` si procede.
    """

    def __init__(self, count: int) -> None:
        super().__init__(f"{count} ricette da rifare sono già state cucinate")
        self.count = count


async def _imported_pages_with(
    session: AsyncSession, term: ImportTerm
) -> list[RecipeImport]:
    """Le pagine già materializzate che contengono questo termine.

    Contenimento JSONB e non una scansione in Python: le pagine importate crescono con
    il ricettario, e caricarle tutte per leggerne una chiave sarebbe la stessa scelta
    che CLAUDE.md segnala su `recipe_search.py` — un limite scritto quando i dati erano
    pochi. Nessun indice nuovo (la feature non aggiunge migrazioni): resta una
    scansione, ma dentro il database e senza materializzare le righe, su
    un'operazione che si fa a mano e di rado.

    `recipe_id IS NOT NULL` distingue una pagina da rifare da una la cui ricetta
    l'utente ha cancellato: quella resta `imported`, perché è lo stato e non la
    presenza della chiave a dire «già importata una volta» (modello `RecipeImport`).
    """
    rows = await session.execute(
        select(RecipeImport).where(
            RecipeImport.source == term.source,
            RecipeImport.state == ImportState.IMPORTED,
            RecipeImport.recipe_id.is_not(None),
            RecipeImport.payload["ingredients"].op("@>")(
                func.jsonb_build_array(func.jsonb_build_object("key", term.term_key))
            ),
        )
    )
    return list(rows.scalars())


async def undo_decision(
    session: AsyncSession, term: ImportTerm, *, force: bool = False
) -> Undone:
    """Rimette il mondo come era prima che quella decisione fosse presa.

    Cinque effetti, in quest'ordine: il controllo sullo storico (che può rifiutare
    prima di toccare qualunque cosa), le pagine e le ricette, l'alias, l'ingrediente,
    il termine. Il controllo viene per primo di proposito: un'eccezione a metà lavoro
    lascerebbe un annullamento incompleto, che è peggio del rifiuto.
    """
    pages = await _imported_pages_with(session, term)
    recipe_ids = [page.recipe_id for page in pages if page.recipe_id is not None]

    if recipe_ids and not force:
        cooked = (
            await session.execute(
                select(func.count())
                .select_from(CookingEvent)
                .where(CookingEvent.recipe_id.in_(recipe_ids))
            )
        ).scalar_one()
        if cooked:
            raise CookedRecipesAffected(cooked)

    # le ricette si rifanno da payload: cancellarle è il modo corretto, non una
    # scorciatoia. `cooking_events.recipe_id` è ON DELETE SET NULL, quindi lo storico
    # sopravvive col suo snapshot.
    requeued = 0
    for page in pages:
        recipe = await session.get(Recipe, page.recipe_id)
        if recipe is not None:
            await session.delete(recipe)
        page.state = ImportState.PENDING
        page.recipe_id = None
        requeued += 1

    ingredient_id: uuid.UUID | None = term.ingredient_id
    alias_forgotten = False
    ingredient_deleted = False

    # il termine si libera prima di provare a cancellare l'ingrediente: finché lo
    # indica, `delete_ingredient_if_unused` lo conta come un uso e rifiuta sempre
    term.decision = TermDecision.PENDING
    term.ingredient_id = None
    term.role_override = None
    term.decided_by = None
    term.decided_at = None
    await session.flush()

    if ingredient_id is not None:
        alias_forgotten = await forget_alias(session, ingredient_id, term.display_name)
        ingredient_deleted = await delete_ingredient_if_unused(session, ingredient_id)

    await session.flush()
    return Undone(
        recipes_requeued=requeued,
        ingredient_deleted=ingredient_deleted,
        alias_forgotten=alias_forgotten,
    )
```

- [ ] **Step 4: Esegui il test del servizio e verifica che passi**

Run: `docker compose exec backend pytest tests/services/test_undo.py -v`
Expected: PASS, 9 test.

- [ ] **Step 5: Scrivi il test della rotta**

In `backend/tests/api/test_imports_undo.py`:

```python
"""La rotta dell'annullamento, e il 409 che chiede conferma sullo storico."""

from sqlalchemy import select

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe import CookingEvent, RecipeSource
from app.db.models.recipe_import import (
    GIALLOZAFFERANO,
    ImportState,
    ImportTerm,
    RecipeImport,
    TermDecision,
)
from app.repositories.ingredients import create_ingredient, remember_alias
from app.repositories.recipes import create_recipe


async def prepara(db_session):
    speck = await create_ingredient(
        db_session, name="speck", display_name="Speck", category=IngredientCategory.CARNE
    )
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-speck", display_name="Speck",
        occurrences=1, decision=TermDecision.MAPPED, ingredient_id=speck.id, decided_by="ai",
    )
    db_session.add(term)
    await db_session.flush()
    await remember_alias(db_session, speck.id, "Speck")
    recipe = await create_recipe(
        db_session, title="Pasta allo speck", description=None, instructions="cuoci",
        servings=2, source=RecipeSource.DATASET, source_ref="https://esempio.invalid/1",
        ingredients=[(speck.id, "primary", None, None)], embedding=None,
    )
    db_session.add(
        RecipeImport(
            source=GIALLOZAFFERANO, url="https://esempio.invalid/1",
            payload={"title": "Pasta allo speck", "ingredients": [{"key": "k-speck"}]},
            state=ImportState.IMPORTED, recipe_id=recipe.id,
        )
    )
    await db_session.flush()
    return term, recipe


async def test_annulla_e_dice_quante_ricette_sono_tornate_in_coda(client, db_session):
    term, _ = await prepara(db_session)
    response = await client.post(f"/api/v1/imports/terms/{term.id}/undo", json={})
    assert response.status_code == 200
    corpo = response.json()
    assert corpo["recipes_requeued"] == 1
    assert corpo["ingredient_deleted"] is True
    assert corpo["remaining_terms"] == 1

    await db_session.refresh(term)
    assert term.decision == TermDecision.PENDING


async def test_una_ricetta_cucinata_risponde_409_col_numero(client, db_session):
    term, recipe = await prepara(db_session)
    db_session.add(CookingEvent(recipe_id=recipe.id, servings=2, snapshot={}))
    await db_session.flush()

    response = await client.post(f"/api/v1/imports/terms/{term.id}/undo", json={})
    assert response.status_code == 409
    # il numero deve stare nel messaggio: è ciò che la schermata mostra
    assert "1" in response.json()["detail"]

    await db_session.refresh(term)
    assert term.decision == TermDecision.MAPPED


async def test_con_force_procede(client, db_session):
    term, recipe = await prepara(db_session)
    db_session.add(CookingEvent(recipe_id=recipe.id, servings=2, snapshot={}))
    await db_session.flush()

    response = await client.post(
        f"/api/v1/imports/terms/{term.id}/undo", json={"force": True}
    )
    assert response.status_code == 200
    await db_session.refresh(term)
    assert term.decision == TermDecision.PENDING


async def test_un_termine_inesistente_risponde_404(client):
    response = await client.post(
        "/api/v1/imports/terms/00000000-0000-0000-0000-000000000000/undo", json={}
    )
    assert response.status_code == 404


async def test_un_termine_ancora_in_coda_non_si_annulla(client, db_session):
    """Non c'è niente da disfare, e un 200 farebbe credere il contrario."""
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-boh", display_name="Boh",
        occurrences=1, decision=TermDecision.PENDING,
    )
    db_session.add(term)
    await db_session.flush()

    response = await client.post(f"/api/v1/imports/terms/{term.id}/undo", json={})
    assert response.status_code == 409
    assert "già in coda" in response.json()["detail"]
```

- [ ] **Step 6: Aggiungi gli schemi e la rotta**

In `backend/app/schemas/recipe_import.py`:

```python
class UndoRequest(BaseModel):
    """`force` è la conferma sullo storico di cottura, non un interruttore generale.

    Serve solo a superare il 409 che avvisa che una delle ricette da rifare è già
    stata cucinata, e che lo storico perderebbe il collegamento.
    """

    force: bool = False


class UndoOut(BaseModel):
    recipes_requeued: int
    ingredient_deleted: bool
    remaining_terms: int
```

In `backend/app/api/imports.py`:

```python
@router.post("/terms/{term_id}/undo", response_model=UndoOut)
async def undo(
    term_id: uuid.UUID,
    payload: UndoRequest,
    session: AsyncSession = Depends(get_session),
) -> UndoOut:
    """Rimette un termine deciso in coda, e con lui il mondo che quella decisione ha mosso.

    Non è un editor: dopo questo, il termine si decide a mano con la scheda di sempre.
    """
    term = await get_term(session, term_id)
    if term is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "termine inesistente")
    if term.decision == TermDecision.PENDING:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"«{term.display_name}» è già in coda: non c'è nessuna decisione da disfare.",
        )

    try:
        undone = await undo_decision(session, term, force=payload.force)
    except CookedRecipesAffected as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{exc.count} di queste ricette le hai già cucinate: rifacendole lo storico "
            "resta ma perde il collegamento. Conferma per procedere.",
        ) from exc

    numbers = await counts(session, GIALLOZAFFERANO)
    await session.commit()
    return UndoOut(
        recipes_requeued=undone.recipes_requeued,
        ingredient_deleted=undone.ingredient_deleted,
        remaining_terms=numbers.pending_terms,
    )
```

Import nuovi: `from app.services.recipe_import.undo import CookedRecipesAffected, undo_decision` e `UndoOut`, `UndoRequest` dagli schemi.

- [ ] **Step 7: Esegui i test e verifica che passino**

Run: `docker compose exec backend pytest tests/api/test_imports_undo.py tests/services/test_undo.py -v`
Expected: PASS, 14 test.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/recipe_import/undo.py backend/app/api/imports.py backend/app/schemas/recipe_import.py backend/tests/services/test_undo.py backend/tests/api/test_imports_undo.py
git commit -m "feat: annullare una decisione dell'AI, con la conferma sullo storico di cottura"
```

---

## Task 11: L'elenco di ciò che l'AI ha deciso

**Files:**
- Modify: `backend/app/api/imports.py`
- Modify: `backend/app/schemas/recipe_import.py`
- Test: `backend/tests/api/test_imports_decided_list.py`

**Interfaces:**
- Consumes: nulla di nuovo.
- Produces:
  - `TermOut` guadagna `decided_by: str | None`, `decided_action: Literal["map", "created", "ignored"] | None`, `decided_name: str | None`
  - `GET /api/v1/imports/terms?decided_by=ai`
  - in `backend/app/repositories/imports.py`: `async def decided_terms(session, source: str, decided_by: str, limit: int = 50) -> list[ImportTerm]`

- [ ] **Step 1: Scrivi il test che fallisce**

In `backend/tests/api/test_imports_decided_list.py`:

```python
"""L'elenco «Deciso dall'AI»: cosa ha fatto, in una riga per termine.

Un termine accorpato non ha niente di speciale: è un `map`, e si mostra come un `map`,
perché è quello che è. Nessuna colonna nuova in tutta la feature.
"""

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.repositories.ingredients import create_ingredient


async def test_lelenco_predefinito_resta_quello_dei_termini_in_coda(client, db_session):
    """Il contratto di oggi non cambia: la coda manuale è la stessa di prima."""
    db_session.add(
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-boh", display_name="Boh",
            occurrences=1, decision=TermDecision.PENDING,
        )
    )
    await db_session.flush()

    response = await client.get("/api/v1/imports/terms")
    assert response.status_code == 200
    nomi = [t["display_name"] for t in response.json()]
    assert nomi == ["Boh"]


async def test_decided_by_ai_torna_solo_le_decisioni_dellai(client, db_session):
    pasta = await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    db_session.add_all([
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-rigatoni", display_name="Rigatoni",
            occurrences=3, decision=TermDecision.MAPPED, ingredient_id=pasta.id,
            decided_by="ai",
        ),
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-penne", display_name="Penne",
            occurrences=2, decision=TermDecision.MAPPED, ingredient_id=pasta.id,
            decided_by="human",
        ),
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-farfalle", display_name="Farfalle",
            occurrences=1, decision=TermDecision.MAPPED, ingredient_id=pasta.id,
            decided_by="auto",
        ),
    ])
    await db_session.flush()

    response = await client.get("/api/v1/imports/terms?decided_by=ai")
    assert response.status_code == 200
    voci = response.json()
    assert [v["display_name"] for v in voci] == ["Rigatoni"]
    assert voci[0]["decided_action"] == "map"
    assert voci[0]["decided_name"] == "pasta"
    assert voci[0]["decided_by"] == "ai"


async def test_un_termine_ignorato_si_riconosce_dallazione(client, db_session):
    db_session.add(
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-acqua", display_name="Acqua",
            occurrences=2, decision=TermDecision.IGNORED, ingredient_id=None,
            decided_by="ai",
        )
    )
    await db_session.flush()

    voci = (await client.get("/api/v1/imports/terms?decided_by=ai")).json()
    assert voci[0]["decided_action"] == "ignored"
    assert voci[0]["decided_name"] is None


async def test_un_decided_by_sconosciuto_e_un_422_non_un_elenco_vuoto(client):
    """Un filtro scritto male che risponde «niente» è indistinguibile da «niente c'è»."""
    response = await client.get("/api/v1/imports/terms?decided_by=nessuno")
    assert response.status_code == 422
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `docker compose exec backend pytest tests/api/test_imports_decided_list.py -v`
Expected: FAIL — il filtro non esiste, la rotta ignora il parametro e torna i `pending`.

- [ ] **Step 3: Aggiungi il repository**

In `backend/app/repositories/imports.py`:

```python
async def decided_terms(
    session: AsyncSession, source: str, decided_by: str, limit: int = 50
) -> list[ImportTerm]:
    """I termini decisi da chi si chiede, i più recenti in cima.

    L'ordine è per data di decisione e non per `occurrences` come la coda: qui si
    rivede quel che è appena stato fatto, e ciò che è appena stato fatto è la cosa che
    più probabilmente si vuole correggere.
    """
    rows = await session.execute(
        select(ImportTerm)
        .where(
            ImportTerm.source == source,
            ImportTerm.decided_by == decided_by,
            ImportTerm.decision != TermDecision.PENDING,
        )
        .order_by(ImportTerm.decided_at.desc().nullslast(), ImportTerm.display_name)
        .limit(limit)
    )
    return list(rows.scalars())
```

- [ ] **Step 4: Cambia lo schema e la rotta**

In `backend/app/schemas/recipe_import.py`, `TermOut` guadagna tre campi:

```python
class TermOut(BaseModel):
    id: uuid.UUID
    display_name: str
    occurrences: int
    suggestion: SuggestionOut | None
    # qualche titolo in attesa: «Scorza di limone» si giudica diversamente in una
    # torta e in un arrosto
    waiting_titles: list[str]
    # Valorizzati solo per un termine già deciso. Servono all'elenco della revisione,
    # che deve dire in una riga cosa è stato fatto: «Rigatoni → pasta», «Speck →
    # creato, carne», «Acqua → ignorato». `decided_action` distingue "map" da
    # "created" perché disfare un ingrediente creato ha una conseguenza in più —
    # l'ingrediente si cancella — e chi legge deve saperlo prima di toccare.
    decided_by: str | None = None
    decided_action: Literal["map", "created", "ignored"] | None = None
    decided_name: str | None = None
```

In `backend/app/api/imports.py`, la rotta `read_terms` diventa:

```python
@router.get("/terms", response_model=list[TermOut])
async def read_terms(
    limit: int = Query(default=20, le=50),
    decided_by: Literal["ai", "human", "auto"] | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[TermOut]:
    """Senza `decided_by`, la coda da decidere. Con, l'elenco di chi l'ha già deciso.

    Una rotta e una forma sola: due rotte con due schemi quasi uguali si scollano, e
    la prima cosa a scollarsi sarebbe il campo che dice cosa è stato deciso.
    """
    if decided_by is not None:
        terms = await decided_terms(session, GIALLOZAFFERANO, decided_by, limit=limit)
        return [
            TermOut(
                id=term.id, display_name=term.display_name, occurrences=term.occurrences,
                suggestion=None, waiting_titles=[], decided_by=term.decided_by,
                decided_action=_decided_action(term),
                decided_name=await _ingredient_name(session, term.ingredient_id),
            )
            for term in terms
        ]

    terms = await pending_terms(session, GIALLOZAFFERANO, limit=limit)
    titles = await waiting_titles(session, GIALLOZAFFERANO, [term.term_key for term in terms])

    out: list[TermOut] = []
    for term in terms:
        match = await match_name(session, term.display_name)
        suggestion = (
            SuggestionOut(
                ingredient_id=match.ingredient_id, name=match.name, certain=match.certain
            )
            if match.ingredient_id is not None and match.name is not None
            else None
        )
        out.append(
            TermOut(
                id=term.id, display_name=term.display_name, occurrences=term.occurrences,
                suggestion=suggestion, waiting_titles=titles.get(term.term_key, []),
            )
        )
    return out


def _decided_action(term: ImportTerm) -> str | None:
    """«map» o «created» non si distinguono guardando il termine, e non serve.

    `import_terms` non registra chi ha creato l'ingrediente, e aggiungere una colonna
    per dirlo violerebbe la regola «nessuna migrazione». Si deduce da un fatto vero e
    già scritto: un ingrediente il cui unico alias dell'import è il nome di questo
    termine è nato con questa decisione. Il caso ambiguo — due termini sullo stesso
    ingrediente — ricade su «map», che è la descrizione prudente: dice meno, non dice
    il falso, e l'annullamento sa comunque cosa fare perché il controllo sugli usi è
    suo e non di questa etichetta.
    """
    if term.decision == TermDecision.IGNORED:
        return "ignored"
    if term.decision == TermDecision.MAPPED:
        return "map"
    return None


async def _ingredient_name(
    session: AsyncSession, ingredient_id: uuid.UUID | None
) -> str | None:
    if ingredient_id is None:
        return None
    ingredient = await session.get(Ingredient, ingredient_id)
    return ingredient.name if ingredient is not None else None
```

Aggiungi `from typing import Literal` in cima e `decided_terms` all'import da `app.repositories.imports`.

> Nota: `_decided_action` non torna mai `"created"` in questa versione, e la docstring dice perché. Lo schema tiene comunque il valore nel `Literal` perché il frontend lo gestisce già e perché il giorno in cui una colonna esisterà non serve toccare due file. Se questo ti sembra un campo mezzo morto, hai ragione a notarlo: il baratto è con la regola «nessuna migrazione», e la spec lo sceglie esplicitamente.

- [ ] **Step 5: Esegui i test e verifica che passino**

Run: `docker compose exec backend pytest tests/api/test_imports_decided_list.py tests/api/test_imports.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/imports.py backend/app/schemas/recipe_import.py backend/app/repositories/imports.py backend/tests/api/test_imports_decided_list.py
git commit -m "feat: GET /imports/terms?decided_by=ai, l'elenco della revisione"
```

---

## Task 12: La coda diventa la revisione

**Files:**
- Modify: `frontend/src/domain/types.ts`
- Modify: `frontend/src/features/recipe-import/api.ts`
- Modify: `frontend/src/features/recipe-import/ImportQueueScreen.tsx`
- Modify: `frontend/src/features/recipe-import/TermCard.tsx`
- Create: `frontend/src/features/recipe-import/DecidedTermRow.tsx`
- Test: `frontend/src/features/recipe-import/ImportQueueScreen.test.tsx` (modifica), `frontend/src/features/recipe-import/DecidedTermRow.test.tsx` (nuovo)

**Interfaces:**
- Consumes: le rotte dei Task 9, 10, 11.
- Produces:
  - `ImportTerm` guadagna `decided_by: string | null`, `decided_action: "map" | "created" | "ignored" | null`, `decided_name: string | null`
  - `TermProposal` sparisce; nuovi `DecideResult`, `UndoResult`
  - `fetchImportTerms(decidedBy?: "ai")`, `decideWithAi(termIds?: string[])`, `undoTerm(termId, force?)`
  - `TermCard` non riceve più `proposal` né `proposalsReady`

- [ ] **Step 1: Aggiorna i tipi e le chiamate**

In `frontend/src/domain/types.ts`: cancella `TermProposal`, estendi `ImportTerm` e aggiungi i due risultati.

```ts
export interface ImportTerm {
  id: string;
  display_name: string;
  /** Quante ricette scaricate aspettano questa decisione. Ordina la coda. */
  occurrences: number;
  suggestion: TermSuggestion | null;
  waiting_titles: string[];
  /** Valorizzati solo per un termine già deciso, cioè solo nell'elenco della
   * revisione: la coda da decidere li ha sempre nulli. */
  decided_by: string | null;
  decided_action: "map" | "created" | "ignored" | null;
  decided_name: string | null;
}

export interface DecideResult {
  applied: number;
  created: number;
  ignored: number;
  still_pending: number;
  unlocked: number;
  remaining_terms: number;
}

export interface UndoResult {
  recipes_requeued: number;
  ingredient_deleted: boolean;
  remaining_terms: number;
}
```

In `frontend/src/features/recipe-import/api.ts`, sostituisci `fetchTermProposals`:

```ts
export function fetchImportTerms(decidedBy?: "ai") {
  const query = decidedBy ? `?decided_by=${decidedBy}` : "";
  return apiFetch<ImportTerm[]>(`/imports/terms${query}`);
}

/** Fa decidere all'AI i termini in coda, e applica. Non torna proposte da
 * confermare: le decisioni si rivedono dall'elenco «Deciso dall'AI». Senza
 * `termIds` vale per tutta la coda, che è il caso del bottone. */
export function decideWithAi(termIds?: string[]) {
  return apiFetch<DecideResult>("/imports/terms/decide", {
    method: "POST",
    body: JSON.stringify(termIds ? { term_ids: termIds } : {}),
  });
}

/** Rimette un termine deciso in coda, e con lui le ricette che ne erano nate.
 * `force` supera il 409 che avvisa di uno storico di cottura da scollegare. */
export function undoTerm(termId: string, force = false) {
  return apiFetch<UndoResult>(`/imports/terms/${termId}/undo`, {
    method: "POST",
    body: JSON.stringify({ force }),
  });
}
```

- [ ] **Step 2: Scrivi il test della riga, che fallisce**

In `frontend/src/features/recipe-import/DecidedTermRow.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DecidedTermRow } from "./DecidedTermRow";
import type { ImportTerm } from "../../domain/types";

function term(overrides: Partial<ImportTerm> = {}): ImportTerm {
  return {
    id: "t1",
    display_name: "Rigatoni",
    occurrences: 3,
    suggestion: null,
    waiting_titles: [],
    decided_by: "ai",
    decided_action: "map",
    decided_name: "pasta",
    ...overrides,
  };
}

describe("DecidedTermRow", () => {
  it("dice a cosa è stato agganciato", () => {
    render(<DecidedTermRow term={term()} pending={false} onUndo={vi.fn()} />);
    expect(screen.getByText("Rigatoni")).toBeInTheDocument();
    expect(screen.getByText(/pasta/)).toBeInTheDocument();
  });

  it("dice quando è stato ignorato, senza nominare un ingrediente", () => {
    render(
      <DecidedTermRow
        term={term({ display_name: "Acqua", decided_action: "ignored", decided_name: null })}
        pending={false}
        onUndo={vi.fn()}
      />
    );
    expect(screen.getByText(/ignorato/i)).toBeInTheDocument();
  });

  it("il pulsante di annullamento nomina il termine", async () => {
    // una riga per termine: senza il nome, chi usa uno screen reader sente N
    // pulsanti «Annulla» identici e non sa quale sta premendo
    const onUndo = vi.fn();
    render(<DecidedTermRow term={term()} pending={false} onUndo={onUndo} />);
    await userEvent.click(
      screen.getByRole("button", { name: /annulla la decisione su «Rigatoni»/i })
    );
    expect(onUndo).toHaveBeenCalledOnce();
  });

  it("mentre una decisione è in corso il pulsante è disabilitato", () => {
    render(<DecidedTermRow term={term()} pending={true} onUndo={vi.fn()} />);
    expect(
      screen.getByRole("button", { name: /annulla la decisione su «Rigatoni»/i })
    ).toBeDisabled();
  });
});
```

- [ ] **Step 3: Esegui il test e verifica che fallisca**

Run: `cd frontend && npx vitest run src/features/recipe-import/DecidedTermRow.test.tsx`
Expected: FAIL — `Failed to resolve import "./DecidedTermRow"`.

- [ ] **Step 4: Scrivi `DecidedTermRow.tsx`**

```tsx
import { buttonClasses } from "../../components/ui/buttonClasses";
import type { ImportTerm } from "../../domain/types";

/** Cosa l'AI ha fatto di questo termine, in una frase.
 *
 * «Rigatoni → pasta» e non «mappato con successo»: il nome dell'ingrediente è la sola
 * informazione su cui si può giudicare se la decisione è giusta, e nasconderla dietro
 * un verbo tecnico renderebbe la revisione una lista di caselle da spuntare.
 *
 * Un termine accorpato dal collasso non ha niente di speciale: è un aggancio, e si
 * mostra come un aggancio, perché è quello che è.
 */
function decisionSummary(term: ImportTerm): string {
  if (term.decided_action === "ignored") return "ignorato: non si tiene in dispensa";
  if (term.decided_action === "created") return `creato: ${term.decided_name ?? "—"}`;
  return `collegato a ${term.decided_name ?? "un ingrediente"}`;
}

export function DecidedTermRow({
  term,
  pending,
  onUndo,
}: {
  term: ImportTerm;
  pending: boolean;
  onUndo: () => void;
}) {
  return (
    <li className="flex items-center justify-between gap-3 border-b border-hairline py-3 last:border-b-0">
      <div className="min-w-0">
        <p className="truncate font-medium">{term.display_name}</p>
        <p className="truncate text-xs text-ink-soft">{decisionSummary(term)}</p>
      </div>
      {/* il nome accessibile porta il termine: una riga per termine, e senza il nome
          chi ascolta sente N pulsanti «Annulla» indistinguibili */}
      <button
        type="button"
        disabled={pending}
        onClick={onUndo}
        aria-label={`Annulla la decisione su «${term.display_name}»`}
        className={buttonClasses("ghost", "inline")}
      >
        Annulla
      </button>
    </li>
  );
}
```

> Nota: `border-hairline` e `buttonClasses("ghost", "inline")` devono esistere. Controlla `frontend/src/index.css` (il blocco `@theme`) e `frontend/src/components/ui/buttonClasses.ts` prima di scrivere: se il token o la variante non ci sono, usa quelli che ci sono. **Non introdurre un colore grezzo**: è la regola in CLAUDE.md, e `grep -rn "emerald\|neutral-" frontend/src` deve restare vuoto.

- [ ] **Step 5: Esegui il test e verifica che passi**

Run: `cd frontend && npx vitest run src/features/recipe-import/DecidedTermRow.test.tsx`
Expected: PASS, 4 test.

- [ ] **Step 6: Riscrivi `ImportQueueScreen`**

Cosa esce, per intero: lo stato `proposalsByTerm`, `missingTermIds`, `proposalsQuery`, `proposalsSettled`, `proposalsFailed`, e le prop `proposal`/`proposalsReady` passate a `TermCard`. Quel codice esisteva per mostrare proposte non applicate, e non ci sono più proposte non applicate.

Cosa entra: la query dei decisi, la mutazione dell'AI, la mutazione dell'annullamento con la conferma del 409.

```tsx
  const { data: decided = [] } = useQuery({
    queryKey: ["import-terms", "ai"],
    queryFn: () => fetchImportTerms("ai"),
  });

  const [undoConfirm, setUndoConfirm] = useState<{ termId: string; message: string } | null>(
    null
  );

  const askAi = useMutation({
    mutationFn: () => decideWithAi(),
    onSuccess: (result) => {
      setLastUnlocked(result.unlocked);
      queryClient.invalidateQueries({ queryKey: ["import-terms"] });
      queryClient.invalidateQueries({ queryKey: ["import-status"] });
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
    },
  });

  const undo = useMutation({
    mutationFn: ({ termId, force }: { termId: string; force: boolean }) =>
      undoTerm(termId, force),
    onSuccess: () => {
      setUndoConfirm(null);
      queryClient.invalidateQueries({ queryKey: ["import-terms"] });
      queryClient.invalidateQueries({ queryKey: ["import-status"] });
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
    },
    onError: (error, variables) => {
      // Il 409 non è un guasto: è la conseguenza sullo storico di cottura, detta
      // prima. Il messaggio arriva dal backend col numero dentro, e mostrarlo è
      // l'unica cosa che permette di decidere se insistere.
      if (error instanceof ApiError && error.status === 409 && !variables.force) {
        setUndoConfirm({ termId: variables.termId, message: error.message });
      }
    },
  });
```

Il markup guadagna, sopra la lista dei `pending`, il bottone dell'AI:

```tsx
      {terms.length > 0 && (
        <button
          type="button"
          disabled={askAi.isPending}
          onClick={() => askAi.mutate()}
          className={buttonClasses("secondary", "block")}
        >
          {askAi.isPending ? "Sto chiedendo…" : "Riprova con l'AI"}
        </button>
      )}

      {askAi.isError && (
        <Alert className="pt-2">
          {askAi.error instanceof ApiError && askAi.error.status === 503
            ? askAi.error.message
            : "Non sono riuscito a chiedere all'AI. Decidi a mano: la coda funziona."}
        </Alert>
      )}
```

e in fondo l'elenco dei decisi:

```tsx
      {decided.length > 0 && (
        <section className="pt-6">
          <h2 className="text-sm font-medium text-ink-soft">Deciso dall'AI</h2>
          <p className="pt-1 text-xs text-ink-faint">
            Ogni riga si può annullare: il termine torna in coda e le ricette che ne
            erano nate si rifanno.
          </p>
          <ul className="pt-2">
            {decided.map((term) => (
              <DecidedTermRow
                key={term.id}
                term={term}
                pending={undo.isPending}
                onUndo={() => undo.mutate({ termId: term.id, force: false })}
              />
            ))}
          </ul>
        </section>
      )}

      {undoConfirm && (
        <div role="alertdialog" aria-label="Conferma l'annullamento" className="pt-3">
          <Alert>{undoConfirm.message}</Alert>
          <div className="flex gap-2 pt-2">
            <button
              type="button"
              disabled={undo.isPending}
              onClick={() => undo.mutate({ termId: undoConfirm.termId, force: true })}
              className={buttonClasses("primary", "inline")}
            >
              Rifai comunque
            </button>
            <button
              type="button"
              onClick={() => setUndoConfirm(null)}
              className={buttonClasses("ghost", "inline")}
            >
              Lascia com'è
            </button>
          </div>
        </div>
      )}
```

In `TermCard.tsx`: togli le prop `proposal` e `proposalsReady` e i due helper `proposalLabel` e `mappedName` che dipendono da `TermProposal`; `shortcut` diventa il solo aggancio testuale, costruito da `term.suggestion`, e `shortcutIsCertain` diventa `term.suggestion?.certain === true`. **Il pulsante ghost dell'aggancio incerto e la sua frase restano**: era una correzione a un difetto critico («Pinoli» che diventava alias di «pisello» con un tocco), e non c'entra con le proposte.

- [ ] **Step 7: Aggiorna il test della schermata**

In `ImportQueueScreen.test.tsx`: cancella i test che riguardano l'arrivo delle proposte e il loro 503, e aggiungi:

```tsx
  it("mostra l'elenco di quel che l'AI ha deciso, con il suo annulla", async () => {
    // il finto di questo file serve già /imports/terms: aggiungi la risposta per
    // ?decided_by=ai usando lo stesso apparato, non un secondo modo di fingere
    renderQueue({
      pending: [],
      decided: [
        {
          id: "t9", display_name: "Rigatoni", occurrences: 3, suggestion: null,
          waiting_titles: [], decided_by: "ai", decided_action: "map",
          decided_name: "pasta",
        },
      ],
    });
    expect(await screen.findByText("Rigatoni")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /annulla la decisione su «Rigatoni»/i })
    ).toBeInTheDocument();
  });

  it("un 409 sull'annullamento chiede conferma invece di fallire", async () => {
    // è l'unico punto della feature in cui si chiede qualcosa: se questo test non
    // c'è, la perdita del collegamento allo storico diventa invisibile
    renderQueue({
      pending: [],
      decided: [
        {
          id: "t9", display_name: "Rigatoni", occurrences: 3, suggestion: null,
          waiting_titles: [], decided_by: "ai", decided_action: "map",
          decided_name: "pasta",
        },
      ],
      undoStatus: 409,
      undoDetail: "1 di queste ricette le hai già cucinate: conferma per procedere.",
    });
    await userEvent.click(
      await screen.findByRole("button", { name: /annulla la decisione su «Rigatoni»/i })
    );
    expect(await screen.findByText(/già cucinate/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /rifai comunque/i })).toBeInTheDocument();
  });
```

> Nota: `renderQueue` con quella forma non esiste. Leggi il file e riusa l'apparato che c'è già — probabilmente un `vi.mock` su `./api` o un finto su `fetch`. Estendilo con le due risposte nuove; non introdurre un secondo modo di fingere le chiamate.

- [ ] **Step 8: Esegui i test del frontend e il type check**

Run: `cd frontend && npx vitest run src/features/recipe-import && npm run typecheck && npm run build`
Expected: PASS tutti e tre. **`tsc --noEmit` non conta**: su questo progetto esce 0 sempre.

- [ ] **Step 9: Verifica che nessun colore grezzo sia entrato**

Run: `grep -rn "emerald\|neutral-\|#[0-9a-fA-F]\{3,6\}" frontend/src --include=*.tsx`
Expected: nessuna riga nei file toccati da questo task.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/domain/types.ts frontend/src/features/recipe-import
git commit -m "feat: la coda diventa la revisione, con l'elenco di quel che l'AI ha deciso"
```

---

## Task 13: La stesura AI sul client nuovo

**Files:**
- Modify: `backend/app/services/ai_recipes.py`
- Modify: `backend/app/schemas/ai.py`
- Modify: `backend/app/api/recipes.py`
- Test: `backend/tests/services/test_ai_recipes.py` (adatta)

**Interfaces:**
- Consumes: `complete_json`, `LlmUnavailable` (Task 2).
- Produces:
  - `DraftIngredient` guadagna `proposed_category: str | None`
  - `DraftIngredientOut` guadagna `proposed_category: str | None`
  - `AiUnavailable` non esiste più: è `LlmUnavailable`
  - `DRAFT_SCHEMA: dict`

- [ ] **Step 1: Scrivi il test che fallisce**

Aggiungi a `backend/tests/services/test_ai_recipes.py`:

```python
async def test_un_ingrediente_ignoto_porta_la_categoria_proposta(db_session, monkeypatch):
    """Serve alla bozza per dire «lo creo io: speck, carne» invece di un campo vuoto.

    La categoria arriva nella stessa risposta: una seconda chiamata per chiederla
    costerebbe il doppio e potrebbe contraddire la prima.
    """
    from app.core.config import get_settings
    from app.services.ai_recipes import draft_recipe

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    try:
        finto = FakeLlm({
            "title": "Pasta allo speck",
            "description": "veloce",
            "instructions": "1. cuoci",
            "servings": 2,
            "ingredients": [
                {"name": "speck", "role": "primary", "quantity_text": "100 g",
                 "category": "carne"}
            ],
        })
        draft = await draft_recipe(db_session, "pasta allo speck", client=finto)
        riga = draft.ingredients[0]
        assert riga.ingredient_id is None  # l'anagrafica non ce l'ha
        assert riga.proposed_category == "carne"
    finally:
        get_settings.cache_clear()


async def test_una_categoria_inventata_non_si_propone(db_session, monkeypatch):
    """Meglio un campo da riempire che una categoria che il salvataggio rifiuterebbe."""
    from app.core.config import get_settings
    from app.services.ai_recipes import draft_recipe

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    try:
        finto = FakeLlm({
            "title": "X", "description": None, "instructions": "1. cuoci", "servings": 2,
            "ingredients": [
                {"name": "speck", "role": "primary", "quantity_text": None,
                 "category": "salumi"}
            ],
        })
        draft = await draft_recipe(db_session, "x", client=finto)
        assert draft.ingredients[0].proposed_category is None
    finally:
        get_settings.cache_clear()
```

> `FakeLlm` viene da `backend/tests/llm_fakes.py` (`from llm_fakes import FakeLlm`), non da un altro file di test: vedi la sezione «Preliminare». Adatta i test già presenti in questo file che iniettavano un finto client Anthropic (`api.messages.create`) al finto di httpx, e rinomina `AiUnavailable` in `LlmUnavailable` dove compare.

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `docker compose exec backend pytest tests/services/test_ai_recipes.py -v`
Expected: FAIL — `AttributeError: 'DraftIngredient' object has no attribute 'proposed_category'`.

- [ ] **Step 3: Riscrivi `ai_recipes.py` sul client nuovo**

Cosa cambia: `_build_client` sparisce, `AiUnavailable` diventa `LlmUnavailable` importata da `app.services.llm`, `MODEL` sparisce (è `OPENROUTER_MODEL`), il prompt guadagna `category`, e arriva uno schema stretto.

```python
DRAFT_MAX_TOKENS = 2000

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": ["string", "null"]},
        "instructions": {"type": "string"},
        "servings": {"type": ["integer", "null"]},
        "ingredients": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string", "enum": ["primary", "secondary"]},
                    "quantity_text": {"type": ["string", "null"]},
                    "category": {"type": "string"},
                },
                "required": ["name", "role", "quantity_text", "category"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "description", "instructions", "servings", "ingredients"],
    "additionalProperties": False,
}
```

Al `SYSTEM_PROMPT` aggiungi in fondo alle regole:

```
- "category" è il reparto di supermercato dell'ingrediente, scelto fra: verdura, frutta, carne, pesce, latticini, cereali, legumi, condimenti, spezie, bevande, dolci, altro. Serve nel caso l'ingrediente non sia ancora in anagrafica.
```

e nello schema descritto a parole dentro il prompt, aggiungi `"category"` alla riga degli ingredienti.

`draft_recipe` diventa:

```python
async def draft_recipe(
    session: AsyncSession, prompt: str, client: object | None = None
) -> RecipeDraft:
    payload = await complete_json(
        system=SYSTEM_PROMPT,
        user=prompt,
        schema=DRAFT_SCHEMA,
        schema_name="bozza_ricetta",
        max_tokens=DRAFT_MAX_TOKENS,
        client=client,
    )
    raw_ingredients = payload.get("ingredients") or []
    if not isinstance(raw_ingredients, list):
        raise LlmUnavailable("la lista degli ingredienti ha una forma inutilizzabile")

    ingredients: list[DraftIngredient] = []
    for entry in raw_ingredients:
        if not isinstance(entry, dict):
            continue
        raw_name = str(entry.get("name", "")).strip()
        if not raw_name:
            continue
        role = (
            IngredientRole.SECONDARY
            if entry.get("role") == IngredientRole.SECONDARY
            else IngredientRole.PRIMARY
        )
        match = await match_name(session, raw_name)
        category = str(entry.get("category") or "").strip().lower()
        ingredients.append(
            DraftIngredient(
                raw_name=raw_name, role=role,
                quantity_text=entry.get("quantity_text") or None,
                ingredient_id=match.ingredient_id, matched_name=match.name,
                confident=match.certain,
                # Solo se l'anagrafica non ce l'ha: proporre una categoria per un
                # ingrediente che esiste già inviterebbe a cambiargliela da una
                # schermata che non è il registro. E solo se è una delle dodici: un
                # campo vuoto da riempire è meglio di un valore che il salvataggio
                # rifiuterebbe.
                proposed_category=(
                    category
                    if match.ingredient_id is None and category in CATEGORIES
                    else None
                ),
            )
        )

    return RecipeDraft(
        title=str(payload.get("title", "Senza titolo")),
        description=payload.get("description") or None,
        instructions=str(payload.get("instructions", "")),
        servings=payload.get("servings"),
        ingredients=ingredients,
    )
```

`CATEGORIES` si importa da `app.services.recipe_import.decide`, che è dove è già definita — oppure, se quell'import incrocia le dipendenze in modo scomodo, si sposta in `app/domain/rules.py` accanto a `SECONDARY_CATEGORIES` e i due la importano da lì. Scegli la seconda se il primo import crea un ciclo.

In `backend/app/schemas/ai.py`, `DraftIngredientOut` guadagna `proposed_category: str | None = None`.

In `backend/app/api/recipes.py`, la rotta `ai_draft` cattura `LlmUnavailable` al posto di `AiUnavailable`, e il messaggio resta quello: `f"stesura AI non disponibile: {exc}"`.

- [ ] **Step 4: Esegui i test e verifica che passino**

Run: `docker compose exec backend pytest tests/services/test_ai_recipes.py tests/api -v`
Expected: PASS. Ogni punto che importa `AiUnavailable` va aggiornato: `grep -rn "AiUnavailable" backend/` deve tornare vuoto.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai_recipes.py backend/app/schemas/ai.py backend/app/api/recipes.py backend/tests/services/test_ai_recipes.py
git commit -m "feat: la stesura AI su OpenRouter, con la categoria proposta per gli ingredienti nuovi"
```

---

## Task 14: Creare l'ingrediente salvando la ricetta

**Files:**
- Modify: `backend/app/schemas/recipe.py`
- Modify: `backend/app/api/recipes.py`
- Modify: `frontend/src/features/ai-draft/AiDraftScreen.tsx`
- Modify: `frontend/src/domain/types.ts`
- Test: `backend/tests/api/test_recipes_create_ingredient.py`, `frontend/src/features/ai-draft/AiDraftScreen.test.tsx`

**Interfaces:**
- Consumes: `proposed_category` (Task 13); `create_ingredient`, `remember_alias` (Task 4).
- Produces: `RecipeIngredientIn` accetta `ingredient_id` **oppure** `name` + `category`, con un validatore che esige uno dei due.

- [ ] **Step 1: Scrivi il test che fallisce**

In `backend/tests/api/test_recipes_create_ingredient.py`:

```python
"""Salvare una ricetta che nomina un ingrediente non ancora in anagrafica.

La creazione avviene **al salvataggio**, non alla stesura: una bozza scartata non deve
lasciare ingredienti dietro, e l'anagrafica cresce solo con ciò che una ricetta salvata
usa davvero. Nella stessa transazione, quindi atomica: nessun ingrediente orfano se il
salvataggio fallisce.
"""

from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.repositories.ingredients import create_ingredient


async def test_una_riga_con_nome_e_categoria_crea_lingrediente(client, db_session):
    payload = {
        "title": "Pasta allo speck",
        "instructions": "1. cuoci",
        "servings": 2,
        "source": "ai",
        "ingredients": [
            {"name": "speck", "category": "carne", "role": "primary", "quantity_text": "100 g"}
        ],
    }
    response = await client.post("/api/v1/recipes", json=payload)
    assert response.status_code == 201

    creato = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "speck"))
    ).scalar_one()
    assert creato.category == "carne"
    assert response.json()["ingredients"][0]["ingredient_name"] == "speck"


async def test_un_nome_che_esiste_gia_si_collega_invece_di_duplicare(client, db_session):
    await create_ingredient(
        db_session, name="speck", display_name="Speck", category=IngredientCategory.CARNE
    )
    payload = {
        "title": "X", "instructions": "1. cuoci", "servings": 2, "source": "ai",
        "ingredients": [{"name": "speck", "category": "pesce", "role": "primary"}],
    }
    response = await client.post("/api/v1/recipes", json=payload)
    assert response.status_code == 201

    quanti = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "speck"))
    ).scalars().all()
    assert len(quanti) == 1
    # la categoria dell'anagrafica vince: il registro è l'autorità, non una bozza
    assert quanti[0].category == "carne"


async def test_una_riga_senza_ne_id_ne_nome_e_un_422(client):
    payload = {
        "title": "X", "instructions": "1. cuoci", "servings": 2, "source": "ai",
        "ingredients": [{"role": "primary"}],
    }
    assert (await client.post("/api/v1/recipes", json=payload)).status_code == 422


async def test_un_nome_senza_categoria_e_un_422(client):
    """Senza categoria non si può creare, e indovinarne una popolerebbe il registro
    di «altro» che nessuno correggerà."""
    payload = {
        "title": "X", "instructions": "1. cuoci", "servings": 2, "source": "ai",
        "ingredients": [{"name": "speck", "role": "primary"}],
    }
    assert (await client.post("/api/v1/recipes", json=payload)).status_code == 422


async def test_se_il_salvataggio_fallisce_nessun_ingrediente_resta_orfano(client, db_session):
    """L'atomicità è il motivo per cui la creazione sta dentro la transazione.

    Due righe con lo stesso ingrediente fanno fallire la ricetta con un 409: se la
    creazione fosse fuori transazione, «speck» resterebbe in anagrafica senza che
    nessuna ricetta lo usi.
    """
    payload = {
        "title": "X", "instructions": "1. cuoci", "servings": 2, "source": "ai",
        "ingredients": [
            {"name": "speck", "category": "carne", "role": "primary"},
            {"name": "speck", "category": "carne", "role": "secondary"},
        ],
    }
    response = await client.post("/api/v1/recipes", json=payload)
    assert response.status_code == 409

    trovati = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "speck"))
    ).scalars().all()
    assert trovati == []
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `docker compose exec backend pytest tests/api/test_recipes_create_ingredient.py -v`
Expected: FAIL — 422 su tutti, perché `ingredient_id` è obbligatorio.

- [ ] **Step 3: Cambia lo schema**

In `backend/app/schemas/recipe.py`:

```python
class RecipeIngredientIn(BaseModel):
    """Un ingrediente esistente, o uno da creare salvando.

    Le due forme stanno in un modello solo perché il salvataggio è uno: due schemi
    separati significherebbero due rotte, o un `Union` che il frontend deve scegliere
    riga per riga. Il validatore è ciò che tiene onesta la scelta.
    """

    ingredient_id: uuid.UUID | None = None
    name: str | None = Field(default=None, max_length=120)
    category: IngredientCategory | None = None
    role: IngredientRole
    quantity_text: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _one_of_the_two(self) -> "RecipeIngredientIn":
        if self.ingredient_id is not None:
            return self
        if not self.name:
            raise ValueError("serve `ingredient_id`, oppure `name` con `category`")
        if self.category is None:
            # indovinare «altro» popolerebbe il registro di voci che nessuno correggerà
            raise ValueError("per creare un ingrediente serve anche `category`")
        return self
```

Aggiungi `from pydantic import BaseModel, Field, model_validator` e `from app.db.models.ingredient import IngredientCategory`.

- [ ] **Step 4: Cambia la rotta**

In `backend/app/api/recipes.py`, dentro `create`, prima della chiamata a `create_recipe`, risolvi le righe:

```python
    # Le righe che nominano un ingrediente non ancora in anagrafica lo creano qui,
    # dentro la stessa transazione della ricetta: se il salvataggio fallisce non resta
    # nessun ingrediente orfano. In sequenza e non in parallelo, per lo stesso motivo
    # del fan-in dell'import: due righe con lo stesso nome nuovo devono diventare un
    # ingrediente, non un doppione.
    resolved: list[tuple[uuid.UUID, str, str | None, str | None]] = []
    for line in payload.ingredients:
        ingredient_id = line.ingredient_id
        if ingredient_id is None:
            # `match_name` e non una ricerca sul solo nome canonico: se la bozza dice
            # «pomodori» e l'anagrafica ha «pomodoro» con quell'alias, collegarsi è
            # giusto e creare sarebbe un duplicato travestito
            match = await match_name(session, line.name or "")
            if match.certain and match.ingredient_id is not None:
                ingredient_id = match.ingredient_id
            else:
                created = await create_ingredient(
                    session, name=line.name or "",
                    display_name=(line.name or "").capitalize(),
                    category=line.category or "altro",
                )
                ingredient_id = created.id
        resolved.append((ingredient_id, line.role, line.quantity_text, line.note))
```

e passa `ingredients=resolved` a `create_recipe`. Aggiungi gli import di `create_ingredient` e `match_name`.

> Nota: il `rollback()` che già c'è nel ramo `IntegrityError` è ciò che rende vero `test_se_il_salvataggio_fallisce_nessun_ingrediente_resta_orfano`. Non toccarlo, e non spostare la creazione fuori dal `try`.

- [ ] **Step 5: Esegui i test e verifica che passino**

Run: `docker compose exec backend pytest tests/api/test_recipes_create_ingredient.py tests/api/test_recipes.py -v`
Expected: PASS. I test esistenti di `test_recipes.py` passano `ingredient_id`, che resta valido.

- [ ] **Step 6: Frontend — «lo creo io»**

In `frontend/src/domain/types.ts`, `DraftIngredient` guadagna `proposed_category: string | null`.

In `AiDraftScreen.tsx`, `FormLine` guadagna `proposedCategory: string | null`, riempito da `lineFromDraft` con `line.proposed_category`; `lineFromIngredient` lo mette a `null`.

Una riga senza `ingredientId` ma con `proposedCategory` diventa salvabile e parte **inclusa**: il modello ha detto cos'è e in che reparto, e non c'è nessun aggancio dubbio da verificare — che è la ragione per cui un aggancio *incerto* parte escluso.

```tsx
  // Una riga si può salvare se è agganciata, o se porta nome e categoria con cui
  // crearla. La seconda forma parte inclusa: non c'è nessun aggancio da verificare,
  // e il selettore della categoria qui sotto è lì per correggerla prima di salvare.
  const savable = lines.filter(
    (line) => line.included && (line.ingredientId !== null || line.proposedCategory !== null)
  );
```

e nella `mutationFn`:

```tsx
        ingredients: savable.map((line) =>
          line.ingredientId !== null
            ? {
                ingredient_id: line.ingredientId,
                role: line.role,
                quantity_text: line.quantityText.trim() === "" ? null : line.quantityText,
              }
            : {
                name: line.label.trim().toLowerCase(),
                category: line.proposedCategory,
                role: line.role,
                quantity_text: line.quantityText.trim() === "" ? null : line.quantityText,
              }
        ),
```

Nel markup della riga, quando `line.ingredientId === null && line.proposedCategory !== null`:

```tsx
                  <div className="flex flex-col gap-1">
                    <p className="text-xs text-ink-soft">
                      Non è in anagrafica: lo creo io salvando.
                    </p>
                    <label className="text-xs font-medium text-ink-soft">
                      Categoria
                      <select
                        aria-label={`Categoria per «${line.label}»`}
                        value={line.proposedCategory ?? "altro"}
                        onChange={(e) =>
                          updateLine(line.key, { proposedCategory: e.target.value })
                        }
                        className="mt-1"
                      >
                        {INGREDIENT_CATEGORIES.map((category) => (
                          <option key={category} value={category}>
                            {category}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
```

Aggiungi l'import di `INGREDIENT_CATEGORIES` da `../../domain/categories`.

- [ ] **Step 7: Scrivi il test del frontend**

Aggiungi a `AiDraftScreen.test.tsx`:

```tsx
  it("un ingrediente ignoto si crea salvando, con la categoria modificabile", async () => {
    // usa l'apparato già presente in questo file per fingere la bozza: cerca come i
    // test esistenti servono POST /recipes/ai-draft e riusa quello
    await mostraBozzaCon([
      {
        raw_name: "speck", role: "primary", quantity_text: "100 g",
        ingredient_id: null, matched_name: null, confident: false,
        proposed_category: "carne",
      },
    ]);

    expect(await screen.findByText(/lo creo io salvando/i)).toBeInTheDocument();
    const categoria = screen.getByLabelText(/categoria per «speck»/i);
    expect(categoria).toHaveValue("carne");

    await userEvent.selectOptions(categoria, "pesce");
    await userEvent.click(screen.getByRole("button", { name: /salva/i }));

    // il corpo mandato porta nome e categoria, non un ingredient_id nullo che il
    // backend rifiuterebbe con un 422
    const corpo = ultimoCorpoDiPost("/recipes");
    expect(corpo.ingredients[0]).toMatchObject({ name: "speck", category: "pesce" });
    expect(corpo.ingredients[0].ingredient_id).toBeUndefined();
  });
```

> `mostraBozzaCon` e `ultimoCorpoDiPost` non esistono con questi nomi: leggi il file e riusa l'apparato che c'è.

- [ ] **Step 8: Esegui i test e il type check**

Run: `cd frontend && npx vitest run src/features/ai-draft && npm run typecheck && npm run build`
Expected: PASS tutti e tre.

- [ ] **Step 9: Commit**

```bash
git add backend/app/schemas/recipe.py backend/app/api/recipes.py backend/tests/api/test_recipes_create_ingredient.py frontend/src/domain/types.ts frontend/src/features/ai-draft
git commit -m "feat: la bozza AI crea l'ingrediente mancante salvando la ricetta"
```

---

## Task 15: Anthropic esce dall'immagine

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/Dockerfile`
- Modify: `backend/tests/test_image_dependencies.py`
- Modify: `backend/tests/conftest.py`

**Interfaces:**
- Consumes: nulla; questo task chiude quel che i Task 7 e 13 hanno reso inutile.
- Produces: nessuna interfaccia nuova.

- [ ] **Step 1: Riscrivi il test dell'immagine**

Sostituisci per intero `backend/tests/test_image_dependencies.py`. La docstring va riscritta, perché il difetto che difendeva non esiste più nella stessa forma: `httpx` è una dipendenza di base e non un extra, quindi non può mancare dall'immagine. Quel che resta da difendere è che **non torni** un extra opzionale sulla strada del modello, e che `anthropic` non rientri di soppiatto.

```python
"""L'immagine deve contenere ciò che le funzionalità richiedono, senza extra sulla strada.

La storia che questo file ricorda: `anthropic` era un extra (`.[ai]`), il Dockerfile
faceva `pip install -e .`, e nell'unico deploy del progetto il pacchetto non esisteva —
quindi la stesura AI rispondeva «pacchetto non installato» con qualunque chiave. Nessun
test poteva accorgersene, perché tutti iniettavano un client finto e l'unico che
arrivava alla costruzione vera usciva sulla chiave assente, prima dell'import.

Da OpenRouter quel difetto è strutturalmente impossibile: il client parla HTTP con
`httpx`, che è una **dipendenza di base**. Quel che resta da difendere è che rimanga
tale, e che `anthropic` non rientri.

La seconda metà di questo file prova la costruzione della richiesta vera. È l'erede del
test che eseguiva `import anthropic`: la lezione di CLAUDE.md — un percorso che nessun
test attraversa è un percorso rotto che nessuno vede — vale per la richiesta esattamente
come valeva per l'import.
"""

import json
import re
import tomllib
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "backend" / "Dockerfile"
PYPROJECT = REPO_ROOT / "backend" / "pyproject.toml"
COMPOSE_FILES = ("docker-compose.yml", "docker-compose.prod.yml")


def righe_unite(testo: str) -> str:
    """Il Dockerfile spezza il RUN su più righe: le continuazioni vanno ricucite."""
    return re.sub(r"\\\s*\n\s*", " ", testo)


def test_httpx_e_una_dipendenza_di_base_e_non_un_extra():
    """Il client del modello ci gira sopra: messo fra gli extra ripeterebbe la storia
    di `anthropic`, e ogni chiamata all'LLM morirebbe su ImportError in produzione."""
    progetto = tomllib.loads(PYPROJECT.read_text())["project"]
    assert any("httpx" in dep for dep in progetto["dependencies"]), (
        f"{PYPROJECT}: httpx non è fra le dipendenze di base ({progetto['dependencies']!r}): "
        "il client di OpenRouter non parte."
    )


def test_anthropic_non_e_piu_una_dipendenza_di_nessun_tipo():
    contenuto = PYPROJECT.read_text()
    assert "anthropic" not in contenuto, (
        f"{PYPROJECT}: `anthropic` è tornata. Il fornitore è OpenRouter, e un secondo "
        "client che nessuno esercita è il difetto in cima a CLAUDE.md."
    )
    extra = tomllib.loads(contenuto)["project"].get("optional-dependencies", {})
    assert "ai" not in extra, f"{PYPROJECT}: l'extra `ai` è tornato ({extra.keys()!r})"


def test_il_dockerfile_non_installa_nessun_extra_ai():
    contenuto = righe_unite(DOCKERFILE.read_text())
    installazioni = [r for r in contenuto.splitlines() if "pip install" in r]
    assert installazioni, f"{DOCKERFILE}: nessun `pip install`, questo test cerca male"
    assert not any("[ai" in r for r in installazioni), (
        f"{DOCKERFILE}: installa ancora un extra `ai` ({installazioni!r}), che non esiste più"
    )


def test_lextra_embeddings_resta_opzionale_e_spento_per_default():
    """torch pesa GB: si accende da `.env`, e da un posto solo.

    Difeso in entrambe le direzioni — che l'interruttore esista e che il default sia
    spento — perché un'immagine che si porta torch dietro a sorpresa è l'altro modo di
    sbagliare.
    """
    contenuto = righe_unite(DOCKERFILE.read_text())
    assert "ARG INSTALL_EMBEDDINGS=0" in contenuto, (
        f"{DOCKERFILE}: manca `ARG INSTALL_EMBEDDINGS=0`, cioè l'interruttore "
        "dell'extra `embeddings` o il suo default spento"
    )
    assert "[embeddings]" in contenuto, (
        f"{DOCKERFILE}: nessun ramo installa l'extra `embeddings`, quindi "
        "INSTALL_EMBEDDINGS=1 non accenderebbe niente"
    )
    for nome_file in COMPOSE_FILES:
        servizio = yaml.safe_load((REPO_ROOT / nome_file).read_text())["services"]["backend"]
        args = servizio.get("build", {}).get("args", {})
        assert "INSTALL_EMBEDDINGS" in args, (
            f"{nome_file}: il servizio backend non passa INSTALL_EMBEDDINGS come argomento "
            f"di build (trovato {servizio.get('build')!r}). Senza, il valore scritto in "
            "`.env` non arriva all'immagine e l'interruttore non esiste."
        )


def test_beautifulsoup_e_una_dipendenza_di_base_e_non_un_extra():
    """Il parser dell'import non è una funzione opzionale."""
    progetto = tomllib.loads(PYPROJECT.read_text())["project"]
    assert any("beautifulsoup4" in dep for dep in progetto["dependencies"]), (
        f"{PYPROJECT}: beautifulsoup4 non è fra le dipendenze di base "
        f"({progetto['dependencies']!r}): il parser dell'import non parte."
    )


async def test_la_richiesta_vera_si_costruisce_per_intero(monkeypatch):
    """L'erede del test che eseguiva `import anthropic`: nessun finto, nessuna rete.

    Costruisce il corpo e gli header che `complete_json` manderebbe, chiamando le
    funzioni vere. È l'unico test che attraversa `build_headers` e
    `build_provider_preferences` insieme al corpo, ed è il posto in cui un errore di
    battitura su `X-Title` o su `require_parameters` si vede.
    """
    import httpx
    import respx

    from app.core.config import get_settings
    from app.services.llm import build_headers, build_provider_preferences, complete_json

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta-per-il-test")
    monkeypatch.setenv("OPENROUTER_APP_URL", "https://esempio.invalid")
    try:
        assert build_headers()["X-Title"] == "Spena Import Ricette"
        assert build_provider_preferences() == {"sort": "price", "require_parameters": True}

        async with respx.mock:
            route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200, json={"choices": [{"message": {"content": '{"ok": true}'}}]}
                )
            )
            await complete_json(
                system="s", user="u",
                schema={
                    "type": "object", "properties": {"ok": {"type": "boolean"}},
                    "required": ["ok"], "additionalProperties": False,
                },
                schema_name="prova", max_tokens=10,
            )
        corpo = json.loads(route.calls.last.request.content)
        assert corpo["model"] == "google/gemma-4-26b-a4b-it"
        assert corpo["response_format"]["json_schema"]["strict"] is True
    finally:
        get_settings.cache_clear()
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `docker compose exec backend pytest tests/test_image_dependencies.py -v`
Expected: FAIL su `test_anthropic_non_e_piu_una_dipendenza_di_nessun_tipo` e `test_il_dockerfile_non_installa_nessun_extra_ai`.

- [ ] **Step 3: Togli l'extra dal `pyproject`**

Cancella la riga `ai = ["anthropic>=0.40"]` da `[project.optional-dependencies]`.

- [ ] **Step 4: Togli l'extra dal Dockerfile**

Il blocco di commento sopra `ARG INSTALL_EMBEDDINGS` parla di `anthropic`: riscrivilo.

```dockerfile
# `sentence-transformers` non si installa per default, e non per gusto: trascina torch,
# che pesa GB (la spec §5 ne stimava 500 MB: è una stima sbagliata). L'applicazione è
# progettata per funzionare senza — la ricerca resta quella testuale su pg_trgm, che è
# la degradazione documentata nella spec §11 — quindi l'extra si accende quando lo si
# vuole, da un posto solo: `INSTALL_EMBEDDINGS=1` in `.env`, che i file Compose passano
# qui come argomento di build. Vedi la riga `EMBEDDING_BACKEND` del README.
#
# Il client del modello linguistico non ha nessun extra: parla HTTP con `httpx`, che è
# una dipendenza di base. È la lezione di `anthropic`, che fra gli extra mancava
# dall'immagine e faceva rispondere «pacchetto non installato» a ogni chiamata.
ARG INSTALL_EMBEDDINGS=0
```

e la riga di installazione:

```dockerfile
RUN pip install --no-cache-dir -e . \
 && if [ "$INSTALL_EMBEDDINGS" = "1" ]; then \
      pip install --no-cache-dir -e ".[embeddings]"; \
    fi
```

- [ ] **Step 5: Aggiorna il commento del conftest**

In `backend/tests/conftest.py`, il commento sopra `Settings.model_config["env_file"] = None` nomina `ANTHROPIC_API_KEY` e un test che non esiste più. Riscrivilo:

```python
# La suite non legge il .env dello sviluppatore. Da quando `env_file` è un percorso
# assoluto (app/core/config.py) quel file viene trovato anche sotto pytest, e un test
# che dimostra il comportamento "variabile non configurata" ricadrebbe in silenzio sul
# valore reale: con OPENROUTER_API_KEY valorizzata, i test che verificano la
# degradazione senza chiave costruirebbero una richiesta vera e farebbero una chiamata a
# pagamento, contro la regola di CLAUDE.md per cui la suite non tocca la rete.
# Neutralizzarlo qui, prima che Settings venga istanziata la prima volta, vale per tutti
# i test presenti e futuri: ciò che un test vuole configurato lo imposta come variabile
# d'ambiente, esplicitamente.
```

- [ ] **Step 6: Esegui la suite intera**

Run: `docker compose exec backend pytest -q`
Expected: PASS. Poi ricostruisci l'immagine e verifica a mano che il pacchetto sia sparito e che il backend parta:

```bash
docker compose up -d --build --wait
docker compose exec backend python -c "import httpx; print('httpx ok')"
docker compose exec backend python -c "import anthropic" 2>&1 | tail -1
```

Il primo comando stampa `httpx ok`, il secondo un `ModuleNotFoundError`.

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/Dockerfile backend/tests/test_image_dependencies.py backend/tests/conftest.py
git commit -m "chore: anthropic esce da dipendenze, immagine e test"
```

---

## Task 16: I documenti

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-09-12-import-ricette-design.md`

**Interfaces:** nessuna. È l'ultimo task e non produce codice.

- [ ] **Step 1: Aggiorna `CLAUDE.md`**

Nella sezione «Stack and layout», la frase su Claude va sostituita:

```
Two external dependencies, each behind its own service with a narrow interface:
`OpenFoodFactsClient` for barcodes and `EmbeddingProvider` for semantic search.
An LLM (`google/gemma-4-26b-a4b-it`, reached through OpenRouter via
`services/llm.py`) drafts recipes and decides the import's unknown ingredient
terms. It never produces nutrient values. There is one provider and one client
on purpose: a second implementation behind a config switch would never run in
production, which is the first defect listed above.
```

Nella sezione «Conventions worth knowing», la riga sull'import va estesa:

```
- **Import brings in recipes, not random new ingredients.** The source catalogue
  is finer than the ingredient registry: `Rigatoni` becomes an alias of `pasta`,
  decided once in `import_terms` and written into `ingredient_aliases`. There is
  no second mapping table, and a wrong decision is corrected from the ingredient
  registry. **The LLM decides these terms and the queue is the review**: every
  decision carries `decided_by = "ai"` and has an undo that puts the term, the
  alias, the created ingredient and the materialized recipes back. A response
  that cannot be verified against the real registry is never applied — the term
  stays in the queue. Specs are
  `docs/superpowers/specs/2026-09-12-import-ricette-design.md` and
  `docs/superpowers/specs/2026-09-13-llm-openrouter-design.md`; the second
  reverses §8.2 of the first.
```

E aggiungi alla lista dei sei punti che «reviews here kept rediscovering» un settimo, perché è costato mezz'ora di diagnosi e non è scritto da nessuna parte:

```
- **A `docker compose` without `-f` replaces production with the dev stack.** Both
  files share the project name `spena`, so `docker compose up -d` on the server
  swaps the prod containers for the dev ones — same volume, no data lost, and no
  Traefik labels, so the domain silently stops resolving to the app. Nothing logs
  an error anywhere: the PWA service worker keeps serving its cached shell while
  every API call fails, which looks exactly like a broken feature. Deploy is
  `docker compose -f docker-compose.prod.yml up -d --build --wait`, always.
```

- [ ] **Step 2: Aggiorna `README.md`**

La sezione «Portare ricette nel ricettario» va riscritta dal secondo paragrafo. Il primo (il comando e la cortesia dello scarico) resta.

```markdown
Dopo lo scarico, gli ingredienti che l'anagrafica non riconosce li decide l'AI: uno per
uno, e quelli che non sa giudicare li lascia in coda. Le ricette entrano da sé, quindi
nel caso normale questo comando è l'unica cosa da fare.

Ci vuole `OPENROUTER_API_KEY` in `.env`. Senza, tutto continua a funzionare a mano: i
termini restano in coda e si decidono dalla riga in cima al ricettario, un tocco
ciascuno, come prima che questa funzione esistesse.

Quel che l'AI ha deciso si rivede da `/ricette/importa`, nell'elenco «Deciso dall'AI»:
ogni riga dice cosa ha fatto — collegato a un ingrediente, creato, ignorato — e si può
annullare. Annullare rimette il termine in coda, cancella l'alias che aveva scritto,
cancella l'ingrediente creato se nessun altro lo usa, e rifà le ricette che ne erano
nate. Se una di quelle ricette l'hai già cucinata, chiede conferma prima: lo storico
sopravvive ma perde il collegamento alla ricetta.

Ogni decisione vale per sempre — diventa un alias dell'ingrediente, e la conosce anche
l'autocomplete della lista — quindi ogni giro costa meno del precedente: un termine già
deciso non torna mai al modello.

Per sapere quale provider di OpenRouter serve il modello e a quanto:

```bash
docker compose exec backend python -m app.cli.llm_prices
```
```

Nella sezione del deploy, la riga del `git pull` va resa esplicita sul `-f`:

```markdown
Un `git pull` e un `docker compose -f docker-compose.prod.yml up -d --build --wait`
bastano. **Il `-f` non è opzionale**: senza, Compose usa `docker-compose.yml`, i due
file condividono il nome di progetto `spena`, e lo stack di produzione viene sostituito
da quello di sviluppo — che non ha le etichette di Traefik. Il dominio smette di
rispondere e non lo scrive nessun log.
```

- [ ] **Step 3: Annota la spec madre**

In `docs/superpowers/specs/2026-09-12-import-ricette-design.md`, in testa a `### 8.2 Le proposte di Claude`, aggiungi:

```markdown
> **Emendato il 2026-09-13.** Questa sezione diceva «Claude propone e non decide».
> Non vale più: il fornitore è OpenRouter con `google/gemma-4-26b-a4b-it`, e l'AI
> **decide**, con la coda che diventa la revisione e un annullamento per ogni
> decisione. Vedi `docs/superpowers/specs/2026-09-13-llm-openrouter-design.md`, §2.
> Quel che resta valido di questa sezione è la verifica di ogni risposta contro
> l'anagrafica vera, che il codice nuovo riusa intatta.
```

- [ ] **Step 4: Verifica finale, a mano e per intero**

Questo è il solo punto del piano in cui si guarda l'applicazione vera. Nessun test della suite può dimostrare quel che segue.

```bash
docker compose up -d --build --wait
docker compose exec backend pytest -q
cd frontend && npm run typecheck && npm run build && npx vitest run; cd ..
grep -rn "emerald\|neutral-" frontend/src && echo "COLORE GREZZO TROVATO" || echo "nessun colore grezzo"
grep -rn "AiUnavailable\|anthropic\|propose_decisions" backend/ --include=*.py && echo "RESIDUO TROVATO" || echo "nessun residuo"
docker compose exec backend python -m app.cli.llm_prices
```

Poi, con `OPENROUTER_API_KEY` configurata in `.env` e i container ricreati:

```bash
docker compose exec backend python -m app.cli.import_gz --limit 5
```

Cosa deve succedere, e cosa guardare se non succede:

1. il comando stampa «N ingredienti riconosciuti da sé» e un numero di ricette importate maggiore di zero. Se stampa «0 importate», leggi i log del backend: una risposta scartata per ogni termine significa che il provider instradato non rispetta lo schema, e `OPENROUTER_PROVIDER_ONLY=darkbloom` è la prova da fare;
2. apri `/ricette`: le ricette nuove ci sono, con foto e tempi;
3. apri `/ricette/importa`: l'elenco «Deciso dall'AI» elenca i termini con cosa è stato fatto di ognuno;
4. premi «Annulla» su una riga: il termine torna nella coda da decidere, e il ricettario perde le ricette che ne erano nate;
5. decidi quel termine a mano con la scheda: le ricette rientrano;
6. apri `/ricette/nuova-ai`, chiedi una ricetta con un ingrediente esotico, e verifica che la riga dica «Non è in anagrafica: lo creo io salvando» con la categoria modificabile. Salva, e controlla che l'ingrediente esista in anagrafica e che la ricetta lo usi.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md docs/superpowers/specs/2026-09-12-import-ricette-design.md
git commit -m "docs: l'AI decide i termini dell'import, e il deploy vuole il -f"
```
