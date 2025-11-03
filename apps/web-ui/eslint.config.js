import { FlatCompat } from '@eslint/eslintrc'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import js from '@eslint/js'
import globals from 'globals'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const compat = new FlatCompat({
  baseDirectory: __dirname,
  recommendedConfig: js.configs.recommended,
  allConfig: js.configs.all,
})

export default [
  {
    ignores: ['dist', 'storybook-static'],
  },
  ...compat.config({
    root: true,
    env: { browser: true, es2020: true },
    extends: [
      'eslint:recommended',
      'plugin:@typescript-eslint/recommended',
      'plugin:react-hooks/recommended',
    ],
    parser: '@typescript-eslint/parser',
    plugins: ['react-refresh'],
    rules: {
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/purity': 'off',
    },
  }),
  {
    files: ['server/**/*.{js,mjs,cjs}'],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
  },
]
