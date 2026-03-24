module.exports = {
  env: {
    browser: true,
    es2021: true,
    node: true,
  },
  extends: ['eslint:recommended'],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
  },
  rules: {
    'no-console': 'off', // Allow console.log during dev
    'no-unused-vars': 'warn', // Warning, not error
    'react/react-in-jsx-scope': 'off',
  },
};
