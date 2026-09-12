// I matcher di jest-dom (toHaveValue, toBeChecked, toBeDisabled) estendono l'interfaccia
// Assertion di vitest. `vitest.setup.ts` li carica a runtime, ma vive nel progetto
// tsconfig.node: l'augmentation non attraversa i confini fra progetti, quindi senza
// questa riga `tsc -b` non conosce i matcher nei test di src/.
import "@testing-library/jest-dom/vitest";
