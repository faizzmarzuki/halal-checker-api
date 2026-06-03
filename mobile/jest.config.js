module.exports = {
  preset: "jest-expo",
  // Run serially: under SDK 55 the parallel RN test workers contend and the
  // async render suites time out. The suite is small, so serial is reliable.
  maxWorkers: 1,
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
  },
};
