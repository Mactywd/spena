"""Il corpo comune dei 503 dell'AI, e le frasi che porta (spec §5)."""

import json

import pytest

from app.api.llm_refusal import llm_refusal
from app.services.llm import LLM_FAILURE_NOTICES, LlmFailureKind, LlmUnavailable

# Copiate dalla spec, §5: chi cambia una frase, cambia la spec.
FRASI_DELLA_SPEC = {
    LlmFailureKind.NOT_CONFIGURED: "L'AI non è collegata: manca la chiave API sul server.",
    LlmFailureKind.AUTH: (
        "L'AI non risponde: la chiave API non vale più (sbagliata o revocata). "
        "Va sostituita nel .env del server."
    ),
    LlmFailureKind.CREDIT: (
        "L'AI non risponde: il credito della chiave API è finito. "
        "Va ricaricato nella console di Anthropic."
    ),
    LlmFailureKind.RATE_LIMIT: (
        "L'AI non risponde: hai raggiunto il limite di frequenza della chiave API, "
        "riprova fra poco."
    ),
    LlmFailureKind.REJECTED: (
        "L'AI non risponde: Anthropic ha rifiutato la richiesta (modello o schema non "
        "accettati). Il dettaglio è nei log del backend."
    ),
    LlmFailureKind.TRANSIENT: "L'AI non risponde in questo momento: riprova fra poco.",
    LlmFailureKind.TRUNCATED: "La risposta dell'AI si è interrotta prima della fine: riprova.",
    LlmFailureKind.REFUSAL: "L'AI ha rifiutato di rispondere a questa richiesta.",
    LlmFailureKind.INVALID: "La risposta dell'AI non si può usare: riprova.",
}


def test_le_frasi_sono_quelle_della_spec():
    assert LLM_FAILURE_NOTICES == FRASI_DELLA_SPEC


@pytest.mark.parametrize("tipo", list(LlmFailureKind))
def test_ogni_tipo_ha_la_sua_frase_nel_503(tipo):
    risposta = llm_refusal(LlmUnavailable("dettaglio-tecnico", kind=tipo))

    assert risposta.status_code == 503
    assert json.loads(risposta.body) == {
        "code": f"llm_{tipo.value}",
        "detail": LLM_FAILURE_NOTICES[tipo],
    }
    assert b"dettaglio-tecnico" not in risposta.body


def test_nessuna_frase_nomina_una_variabile():
    for frase in LLM_FAILURE_NOTICES.values():
        assert "ANTHROPIC_API_KEY" not in frase
        assert "HTTP" not in frase
        assert "stop_reason" not in frase
