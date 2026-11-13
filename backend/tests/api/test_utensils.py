import uuid

U = "/api/v1/utensils"


async def test_senza_utensili_l_elenco_e_vuoto(logged_client):
    risposta = await logged_client.get(U)
    assert risposta.status_code == 200
    assert risposta.json() == []


async def test_aggiungere_correggere_togliere(logged_client):
    creato = await logged_client.post(U, json={"name": "padella antiaderente", "note": "da 24 cm"})
    assert creato.status_code == 201
    utensile = creato.json()
    assert utensile["name"] == "padella antiaderente" and utensile["note"] == "da 24 cm"
    assert set(utensile) == {"id", "name", "note"}

    corretto = await logged_client.patch(f"{U}/{utensile['id']}", json={"note": "da 28 cm"})
    assert corretto.status_code == 200
    assert corretto.json() == {**utensile, "note": "da 28 cm"}

    rinominato = await logged_client.patch(f"{U}/{utensile['id']}", json={"name": "padella"})
    assert rinominato.json() == {**utensile, "name": "padella", "note": "da 28 cm"}

    assert (await logged_client.get(U)).json() == [rinominato.json()]
    assert (await logged_client.delete(f"{U}/{utensile['id']}")).status_code == 204
    assert (await logged_client.get(U)).json() == []


async def test_l_elenco_va_per_nome_senza_badare_alle_maiuscole(logged_client):
    for nome in ["padella", "Frusta elettrica", "colino"]:
        await logged_client.post(U, json={"name": nome})
    assert [u["name"] for u in (await logged_client.get(U)).json()] == [
        "colino", "Frusta elettrica", "padella",
    ]


async def test_il_nome_e_la_nota_si_scrivono_su_una_riga_sola(logged_client):
    # un testo incollato non deve portare righe nuove nel prompt (decisione 6)
    creato = await logged_client.post(
        U, json={"name": "  padella\n\n\tantiaderente  ", "note": "\n da 24\tcm "}
    )
    assert creato.json()["name"] == "padella antiaderente"
    assert creato.json()["note"] == "da 24 cm"
    corretto = await logged_client.patch(
        f"{U}/{creato.json()['id']}", json={"name": "frusta\r\nelettrica"}
    )
    assert corretto.json()["name"] == "frusta elettrica"


async def test_un_nome_vuoto_o_troppo_lungo_e_un_422(logged_client):
    assert (await logged_client.post(U, json={"name": "   "})).status_code == 422
    assert (await logged_client.post(U, json={"name": "x" * 121})).status_code == 422
    assert (await logged_client.post(U, json={"name": "x" * 120})).status_code == 201
    assert (await logged_client.post(U, json={"name": "colino", "note": "y" * 201})).status_code == 422
    creato = (await logged_client.post(U, json={"name": "colino"})).json()
    assert (await logged_client.patch(f"{U}/{creato['id']}", json={"name": "  "})).status_code == 422
    assert (await logged_client.patch(f"{U}/{creato['id']}", json={"name": None})).status_code == 422


async def test_una_nota_vuota_e_nessuna_nota(logged_client):
    creato = (await logged_client.post(U, json={"name": "colino", "note": "   "})).json()
    assert creato["note"] is None
    con_nota = (await logged_client.patch(f"{U}/{creato['id']}", json={"note": "a maglia fine"})).json()
    assert con_nota["note"] == "a maglia fine"
    assert (await logged_client.patch(f"{U}/{creato['id']}", json={"note": None})).json()["note"] is None
    await logged_client.patch(f"{U}/{creato['id']}", json={"note": "a maglia fine"})
    assert (await logged_client.patch(f"{U}/{creato['id']}", json={"note": ""})).json()["note"] is None


async def test_una_patch_senza_campi_e_un_400(logged_client):
    creato = (await logged_client.post(U, json={"name": "colino"})).json()
    assert (await logged_client.patch(f"{U}/{creato['id']}", json={})).status_code == 400


async def test_un_utensile_che_non_c_e_e_un_404(logged_client):
    assente = uuid.uuid4()
    assert (await logged_client.patch(f"{U}/{assente}", json={"name": "colino"})).status_code == 404
    assert (await logged_client.delete(f"{U}/{assente}")).status_code == 404


async def test_due_utensili_con_lo_stesso_nome_convivono(logged_client):
    # due padelle di misure diverse sono due utensili veri (decisione 5)
    await logged_client.post(U, json={"name": "padella antiaderente", "note": "da 24 cm"})
    await logged_client.post(U, json={"name": "padella antiaderente", "note": "da 28 cm"})
    assert sorted(u["note"] for u in (await logged_client.get(U)).json()) == ["da 24 cm", "da 28 cm"]


async def test_senza_sessione_non_si_legge_ne_si_scrive(client):
    assert (await client.get(U)).status_code == 401
    assert (await client.post(U, json={"name": "colino"})).status_code == 401
