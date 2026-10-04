// Flat config baked into the JavaScript runner image.
// Style, complexity and security rules tuned for beginner course submissions.
import security from 'eslint-plugin-security'

export default [
  {
    files: ['**/*.js', '**/*.mjs', '**/*.cjs'],
    plugins: { security },
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: 'module',
      globals: {
        console: 'readonly',
        process: 'readonly',
        require: 'readonly',
        module: 'writable',
        __dirname: 'readonly',
        Buffer: 'readonly',
        setTimeout: 'readonly',
        setInterval: 'readonly',
        fetch: 'readonly',
        document: 'readonly',
        window: 'readonly',
      },
    },
    rules: {
      // bug risk
      'no-undef': 'error',
      'no-unused-vars': 'warn',
      'eqeqeq': 'warn',
      'no-var': 'warn',
      'prefer-const': 'warn',
      'no-fallthrough': 'error',
      'no-unreachable': 'error',
      'no-constant-condition': 'warn',
      'no-dupe-keys': 'error',
      'no-self-assign': 'error',

      // complexity
      'complexity': ['warn', 10],
      'max-depth': ['warn', 4],
      'max-lines-per-function': ['warn', { max: 60, skipBlankLines: true, skipComments: true }],

      // security
      'no-eval': 'error',
      'no-implied-eval': 'error',
      'no-new-func': 'error',
      'security/detect-eval-with-expression': 'error',
      'security/detect-child-process': 'warn',
      'security/detect-unsafe-regex': 'warn',
      'security/detect-non-literal-require': 'warn',
      'security/detect-pseudoRandomBytes': 'warn',
    },
  },
]
