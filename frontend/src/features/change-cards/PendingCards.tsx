import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Card } from "../../components/ui/Card";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { PENDING_CARDS_KEY, fetchPendingCards } from "./api";

/** Le schede dei cambi ancora da applicare; vuoto, niente a video. */
export function PendingCards() {
  const cards = useQuery({ queryKey: PENDING_CARDS_KEY, queryFn: fetchPendingCards });
  if (!cards.data || cards.data.length === 0) return null;
  return (
    <section>
      <SectionHeading>Schede dei cambi da applicare</SectionHeading>
      <Card pad={false}>
        <ul>
          {cards.data.map((c) => (
            <li key={c.id} className="flex items-center justify-between gap-2 px-3 py-1">
              <span className="min-w-0 break-words text-sm">{c.title}</span>
              <Link to={`/pasti/cambi/${c.id}`} className={buttonClasses("secondary", "pill")}>
                Apri
              </Link>
            </li>
          ))}
        </ul>
      </Card>
    </section>
  );
}
