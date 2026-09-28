import { Link } from "react-router-dom";
import { Screen } from "../../components/ui/Screen";
import { EmptyState } from "../../components/ui/EmptyState";
import { buttonClasses } from "../../components/ui/buttonClasses";

/** Un indirizzo che non porta a niente — un collegamento vecchio, un refuso. Prima
 * di questa schermata restava una pagina vuota sotto l'intestazione (dal giro di T3),
 * cioè un vicolo cieco. */
export function NotFoundScreen() {
  return (
    <Screen title="Pagina non trovata">
      <EmptyState
        title="Questo indirizzo non porta a niente"
        body="Forse è un collegamento vecchio. Da qui torni dove si comincia."
        action={
          <Link to="/lista" className={buttonClasses("primary")}>
            Torna alla lista
          </Link>
        }
      />
    </Screen>
  );
}
