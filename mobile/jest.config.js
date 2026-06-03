module.exports = {
  preset: "jest-expo",
  // Run serially with a generous timeout: the RN/jest-expo test environment
  // leaks handles that accumulate across suites, slowing later async-render
  // suites (each passes in isolation). maxWorkers:1 + a higher timeout keeps it
  // reliable; the `test` script adds --forceExit so Jest exits despite the leak.
  maxWorkers: 1,
  testTimeout: 20000,
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
  },
};
