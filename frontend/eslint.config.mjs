import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const compat = new FlatCompat({ baseDirectory: __dirname });

const config = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    ignores: [".next/**", "node_modules/**", "next-env.d.ts"],
  },
  {
    rules: {
      // SPEC §13.5 — item text is user content and is rendered as text everywhere.
      // There are no exceptions to this one, so it is an error, not a warning.
      "react/no-danger": "error",
      "@typescript-eslint/no-explicit-any": "error",
    },
  },
];

export default config;
