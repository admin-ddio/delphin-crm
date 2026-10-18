import js from '@eslint/js';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  {
    ignores: [
      'dist',
      'coverage',
      'playwright-report',
      'test-results',
      'node_modules',
      'src/api/schema.d.ts',
    ],
  },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended, jsxA11y.flatConfigs.recommended],
    plugins: { 'react-hooks': reactHooks },
    languageOptions: {
      ecmaVersion: 2022,
      globals: { ...globals.browser },
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      '@typescript-eslint/consistent-type-imports': 'error',
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', ignoreRestSiblings: true },
      ],
      // Feature code goes through TanStack Query + the generated client, never raw fetch.
      'no-restricted-globals': ['error', { name: 'fetch', message: 'Use lib/api-client.ts.' }],
    },
  },
  {
    files: ['tests/**/*.{ts,tsx}', '*.config.{ts,js}', 'src/lib/api-client.ts'],
    languageOptions: { globals: { ...globals.node, ...globals.browser } },
    rules: { 'no-restricted-globals': 'off' },
  },
);
