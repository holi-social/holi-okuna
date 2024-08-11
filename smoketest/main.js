import http from "k6/http";
import { check, sleep } from "k6";
import exec from "k6/execution";

// This configuration only executes 1 test, enough for a smoketest
export const options = {
  vus: 1,
  iterations: 1,
};

export default () => {
  // define the graphql request
  const params = {
    headers: {
      "Content-Type": "application/json",
    },
  };
  const query = `query{topics{totalResults}}`;

  // perform the graphql request
  const response = http.post(
    `${__ENV.BASE_URL}`,
    JSON.stringify({ query }),
    params,
  );

  // define the tests
  const testResults = [
    check(response, {
      "is status 200": (r) => r.status === 200,
    }),
    check(JSON.parse(response.body), {
      // there can be multiple tests here, e.g.
      //"contains topics object": (r) => typeof r.data.topics != null,
      "contains totalResults count": (r) =>
        typeof r.data.topics.totalResults == "number",
    }),
  ];

  // fail on any unmet expectations. We need to do this explicitly, because k6 is a load testing tool
  if (testResults.includes(false)) {
    exec.test.abort("smoke test failed");
  }
};
