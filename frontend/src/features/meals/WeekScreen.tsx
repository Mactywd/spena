import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { Card } from "../../components/ui/Card";
import { Chip } from "../../components/ui/Chip";
import { ErrorState } from "../../components/ui/ErrorState";
import { IconChevronLeft, IconChevronRight } from "../../components/ui/icons";
import { Screen } from "../../components/ui/Screen";
import type { Meal, MealSlot } from "../../domain/types";
import { fetchWeek } from "./api";
import { SLOT_LABELS, dayLabel, mealMarks, weekLabel } from "./format";

const SLOTS: MealSlot[] = ["lunch", "dinner"];
const ARROW = "inline-flex size-11 items-center justify-center rounded-full text-ink-soft";

/** La settimana, da lunedì a domenica (spec 2026-11-12 §5.1). Il lunedì, «oggi» e
 * «non registrata» li decide il server: qui si mostra ciò che arriva. Spostare e
 * cancellare si fa dalla schermata del piatto, non da qui (decisione 12). */
export function WeekScreen() {
  const [params] = useSearchParams();
  const of = params.get("settimana");
  const week = useQuery({ queryKey: ["meals", "week", of], queryFn: () => fetchWeek(of) });

  return (
    <Screen title="Pasti">
      {week.isError ? (
        <ErrorState
          message="La settimana non si carica."
          onRetry={() => week.refetch()}
          retrying={week.isFetching}
        />
      ) : !week.data ? (
        <p className="text-sm text-ink-soft">Carico la settimana…</p>
      ) : (
        <>
          <div className="flex items-center justify-between gap-2 pb-2">
            <Link
              to={`/pasti?settimana=${week.data.previous}`}
              aria-label="Settimana prima"
              className={ARROW}
            >
              <IconChevronLeft aria-hidden="true" className="size-6" />
            </Link>
            <span className="text-sm font-medium">
              {weekLabel(week.data.monday, week.data.sunday)}
            </span>
            <Link
              to={`/pasti?settimana=${week.data.next}`}
              aria-label="Settimana dopo"
              className={ARROW}
            >
              <IconChevronRight aria-hidden="true" className="size-6" />
            </Link>
          </div>
          {(week.data.today < week.data.monday || week.data.today > week.data.sunday) && (
            <Link to="/pasti" className="mb-2 inline-flex min-h-11 items-center text-sm font-medium text-brand">
              Torna a oggi
            </Link>
          )}
          <ul className="flex flex-col gap-2">
            {week.data.days.map((day) => (
              <DayCard
                key={day}
                day={day}
                isToday={day === week.data.today}
                meals={week.data.meals.filter((m) => m.day === day)}
              />
            ))}
          </ul>
        </>
      )}
      {/* qui, sotto la settimana, il piano 4 mette «Pianifica con Claude» */}
    </Screen>
  );
}

function DayCard({ day, isToday, meals }: { day: string; isToday: boolean; meals: Meal[] }) {
  return (
    <Card as="li" className={isToday ? "bg-brand-tint" : ""}>
      <div aria-current={isToday ? "date" : undefined}>
        <h2 className="text-sm font-semibold">
          {dayLabel(day)}
          {isToday && <span className="pl-2 text-xs font-medium text-brand">oggi</span>}
        </h2>
        {SLOTS.map((slot) => {
          const meal = meals.find((m) => m.slot === slot);
          return (
            <div key={slot} className="pt-1.5">
              <p className="text-xs text-ink-soft">{SLOT_LABELS[slot]}</p>
              {meal ? (
                <MealLink meal={meal} />
              ) : (
                <Link
                  to={`/pasti/nuovo?giorno=${day}&posto=${slot}`}
                  className="flex min-h-11 items-center text-sm text-ink-soft"
                >
                  + da pianificare
                </Link>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function MealLink({ meal }: { meal: Meal }) {
  const marks = mealMarks(meal);
  return (
    <Link
      to={`/pasti/${meal.id}`}
      className="flex min-h-11 items-center justify-between gap-2"
    >
      <span className="min-w-0">
        <span className="block break-words text-sm font-medium">{meal.dish}</span>
        {meal.sides && <span className="block break-words text-xs text-ink-soft">{meal.sides}</span>}
      </span>
      <span className="flex shrink-0 flex-wrap justify-end gap-1">
        {marks.map((mark) => (
          <Chip key={mark} tone="bg-low-tint text-ink">
            {mark}
          </Chip>
        ))}
      </span>
    </Link>
  );
}
