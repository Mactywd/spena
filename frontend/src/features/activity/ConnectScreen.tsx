import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { ErrorState } from "../../components/ui/ErrorState";
import { Screen } from "../../components/ui/Screen";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { createToken, fetchActivity, headersJson, webhookUrl } from "./api";
import { CopyField } from "./CopyField";
import { connectionText } from "./format";
import type { NewToken } from "./types";

/** «Collega HC Webhook» (H2): la chiave del webhook e i passi da fare sul telefono.
 *
 * La chiave si vede una volta sola, appena creata, e vive solo nello stato di questa
 * schermata: uscendo si perde, e la si rigenera. Il server ne tiene l'impronta. Rigenerare
 * chiede una conferma, perché spegne quella che HC Webhook sta usando. */
export function ConnectScreen() {
  const queryClient = useQueryClient();
  const activity = useQuery({ queryKey: ["activity"], queryFn: fetchActivity });
  const [fresh, setFresh] = useState<NewToken | null>(null);
  const [confirming, setConfirming] = useState(false);
  const create = useMutation({
    mutationFn: createToken,
    onSuccess: (token) => {
      setFresh(token);
      setConfirming(false);
      void queryClient.invalidateQueries({ queryKey: ["activity"] });
    },
  });

  let key: ReactNode;
  if (fresh) {
    key = (
      <>
        <p className="text-sm">Ecco la chiave. Si vede solo adesso: copiala in HC Webhook prima di uscire da qui.</p>
        <CopyField label="Chiave" value={fresh.token} />
      </>
    );
  } else if (activity.isPending) {
    key = <p className="text-sm text-ink-soft">Carico…</p>;
  } else if (activity.isError) {
    key = (
      <ErrorState
        message="Non sono riuscito a leggere la chiave."
        onRetry={() => activity.refetch()}
        retrying={activity.isFetching}
      />
    );
  } else if (!activity.data.connection.has_token) {
    key = (
      <>
        <p className="text-sm">
          Spena accetta i dati solo da chi porta la sua chiave. Creala, poi incollala in HC Webhook come dicono i
          passi qui sotto.
        </p>
        <Button variant="primary" onClick={() => create.mutate()} busy={create.isPending}>
          Crea la chiave
        </Button>
      </>
    );
  } else if (!confirming) {
    key = (
      <>
        <p className="text-sm">{connectionText(activity.data.connection, activity.data.today)}</p>
        <p className="text-sm text-ink-soft">
          La chiave si vede solo quando la crei. Se non l'hai più, rigenerala: quella di prima smette di funzionare.
        </p>
        <Button onClick={() => setConfirming(true)}>Rigenera la chiave</Button>
      </>
    );
  } else {
    key = (
      <>
        <p className="text-sm">
          La chiave di adesso smetterà di funzionare, e in HC Webhook andrà incollata quella nuova.
        </p>
        <div className="flex gap-2">
          <Button variant="primary" onClick={() => create.mutate()} busy={create.isPending}>
            Rigenera
          </Button>
          <Button variant="ghost" onClick={() => setConfirming(false)}>
            Annulla
          </Button>
        </div>
      </>
    );
  }

  return (
    <Screen
      title="Collega HC Webhook"
      subtitle="Una volta sola, dal telefono con Samsung Health."
      back={{ to: "/attivita", label: "Attività" }}
    >
      <SectionHeading>La chiave</SectionHeading>
      <Card className="flex flex-col items-start gap-3">
        {key}
        {create.isError && <Alert>Non sono riuscito a creare la chiave.</Alert>}
      </Card>
      <SectionHeading>In HC Webhook</SectionHeading>
      <Card>
        <ol aria-label="I passi in HC Webhook" className="list-decimal space-y-3 pl-5 text-sm">
          <li>
            In Samsung Health: Impostazioni › Health Connect. Lascia scrivere a Samsung Health passi, esercizio e
            peso, e tieni attiva la sincronizzazione con Samsung Cloud.
          </li>
          <li>Installa HC Webhook (Health Connect to Webhook) da Google Play.</li>
          <li>
            Aprila e attiva Passi, Sessioni di esercizio e Peso fra i «Tipi di dati»; concedi i permessi di Health
            Connect, anche quello in background.
          </li>
          <li>
            Alla voce «Risoluzione passi» lascia «Giornaliero»: così Health Connect conta una volta sola i passi del
            telefono e dell'orologio.
          </li>
          {/* un `div` dentro il `li`, e non `flex` sul `li`: un `li` flessibile perde il
              suo numero */}
          <li>
            <div className="flex flex-col gap-2">
              <span>In «Webhook» aggiungi questo indirizzo:</span>
              <CopyField label="Indirizzo" value={webhookUrl()} />
            </div>
          </li>
          <li>
            <div className="flex flex-col gap-2">
              <span>Nel webhook, «Gestisci intestazioni» › «JSON»: incolla questo e tocca «Applica JSON».</span>
              {fresh ? (
                <CopyField label="Intestazioni (JSON)" value={headersJson(fresh)} />
              ) : (
                <span className="text-ink-soft">Le intestazioni da incollare compaiono qui quando crei la chiave.</span>
              )}
            </div>
          </li>
          <li>Sempre nel webhook, fra i «Tipi di dati» scegli solo Passi, Sessioni di esercizio e Peso.</li>
          <li>
            Tocca «Testa Webhook»: in «Attività», l'ultima sincronizzazione deve dire che è arrivata la prova.
          </li>
          <li>
            Intervallo: 15 minuti o più. E togli HC Webhook dall'ottimizzazione della batteria («Ottimizzazione
            batteria attiva» › «Risolvi ora»), o Android salta le sincronizzazioni.
          </li>
          <li>Per portare i giorni passati: «Sincronizzazione manuale» › «Ultimi 30 giorni».</li>
        </ol>
      </Card>
    </Screen>
  );
}
