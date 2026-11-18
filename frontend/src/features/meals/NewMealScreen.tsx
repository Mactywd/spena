import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Alert } from "../../components/ui/Alert";
import { useNotice } from "../../components/ui/noticeContext";
import { Screen } from "../../components/ui/Screen";
import { buttonClasses } from "../../components/ui/buttonClasses";
import type { MealSlot } from "../../domain/types";
import { MEALS_KEY, createMeal, fetchLeftoverCandidates } from "./api";
import { MealForm } from "./MealForm";
import { SLOT_LABELS, longDayLabel } from "./format";

const DAY = /^\d{4}-\d{2}-\d{2}$/;

/** Un posto vuoto della settimana, scritto a mano (spec 2026-11-12 §5.2). */
export function NewMealScreen() {
  const [params] = useSearchParams();
  const day = params.get("giorno") ?? "";
  const slotParam = params.get("posto");
  const slot: MealSlot | null =
    slotParam === "lunch" || slotParam === "dinner" ? slotParam : null;
  const valid = DAY.test(day) && slot !== null;

  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const notice = useNotice();
  const candidates = useQuery({
    queryKey: [...MEALS_KEY, "leftover", day, slot],
    queryFn: () => fetchLeftoverCandidates(day, slot!),
    enabled: valid,
  });

  if (!valid) {
    return (
      <Screen title="Nuovo pasto" back={{ to: "/pasti", label: "Pasti" }}>
        <Alert tone="note">Non so di quale posto si tratta.</Alert>
        <Link to="/pasti" className="inline-flex min-h-11 items-center text-sm font-medium text-brand">
          Scegli un posto nella settimana
        </Link>
      </Screen>
    );
  }

  return (
    <Screen
      title="Nuovo pasto"
      subtitle={`${longDayLabel(day)} · ${SLOT_LABELS[slot]}`}
      back={{ to: `/pasti?settimana=${day}`, label: "Pasti" }}
    >
      {/* il posto passa alla pianificazione, che ci punta la conversazione */}
      <Link
        to={`/pasti/pianifica?giorno=${day}&posto=${slot}`}
        className={`${buttonClasses("secondary", "block")} mb-3`}
      >
        Chiedilo a Claude
      </Link>
      <MealForm
        initial={{ day, slot, dish: "", sides: null, away: false, leftover_of_id: null }}
        slotEditable={false}
        // se l'elenco non arriva il modulo resta quello di sempre, senza «Avanzo di»
        leftoverChoices={candidates.data ?? []}
        submitLabel="Salva"
        save={createMeal}
        onSaved={() => {
          void queryClient.invalidateQueries({ queryKey: MEALS_KEY });
          notice({ text: "Pasto salvato." });
          navigate(`/pasti?settimana=${day}`);
        }}
      />
    </Screen>
  );
}
