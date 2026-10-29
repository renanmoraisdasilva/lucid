import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules", "coverage"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      "max-lines": ["error", { max: 200 }],
      complexity: ["error", 12],
      "max-depth": ["error", 4],
      "max-params": ["error", 5],
    },
  },
  {
    files: ["src/lib/**/*.ts", "src/api/**/*.ts"],
    ignores: ["**/*.{test,spec}.{ts,tsx}"],
    rules: {
      "max-lines-per-function": ["error", { max: 50 }],
    },
  },
  {
    files: ["**/*.{test,spec}.{ts,tsx}", "src/test/**/*.{ts,tsx}"],
    rules: {
      "max-lines": ["error", { max: 400 }],
      "max-params": "off",
    },
  },
);
