const express = require('express')
const { graphqlHTTP } = require('express-graphql')
const { createGraphQLSchema } = require('openapi-to-graphql')
const { readFileSync } = require('fs')
const yaml = require('js-yaml');

async function main(oas) {
  // generate schema:
  const { schema, report } = await createGraphQLSchema(oas, {
      headers: function(method, path, title, { source, args, context, info }){
        return context.headers
      }
  })
  // server schema:
  const app = express()
  app.use(
    '/graphql',
    graphqlHTTP({
      schema,
      graphiql: true
    })
  )
  app.listen(3000)
}
const fileContents = readFileSync('./schema.yml', 'utf8');
const oas = yaml.load(fileContents);
main(oas) // oas loaded/constructed someplace else

