import { apiFetch } from "../../api/client";
import type { Spending, SpendingPeriod } from "./types";

export function fetchSpending(period: SpendingPeriod) {
  return apiFetch<Spending>(`/llm-spending?period=${period}`);
}
