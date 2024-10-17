import http from 'k6/http'
import { check, sleep } from 'k6'
import exec from 'k6/execution'

// You don't need to change anything in this section, it's k6 glue code.
// See the default function at the end of the file for defining your smoketest.
// This configuration only executes 1 test, enough for a smoketest.
export const options = {
  vus: 1,
  iterations: 1,
}

/**
 * Performs a GraphQL query and checks the response using the provided function. Fails if any of the provided expectations are not met.
 * @param {string} query The GraphQL query to perform
 * @param {(response: http.Response) => Array<boolean>} checkFunction
 *   A function that takes the HTTP response as an argument and returns an array
 *   of boolean values, each indicating success or failure of a test.
 */
function forQuery(query, checkFunction) {
  const response = http.post(`${__ENV.BASE_URL}`, JSON.stringify({ query }), {
    headers: { 'Content-Type': 'application/json' },
  })
  const testResults = checkFunction(response)

  // fail on any unmet expectations. We need to do this explicitly, because k6 is a load testing tool that continues on errors by default.
  if (testResults.includes(false)) {
    exec.test.abort('smoke test failed')
  }
}

// Define your smoketest(s) here.
export default () => {
  forQuery(`query{topics{totalResults}}`, (response) => [
    check(response, {
      'is status 200': (r) => r.status === 200,
    }),
    check(JSON.parse(response.body), {
      // there can be multiple tests here, e.g.
      //"contains topics object": (r) => typeof r.data.topics != null,
      'contains totalResults count': (r) => typeof r.data.topics.totalResults == 'number',
    }),
  ])
}
