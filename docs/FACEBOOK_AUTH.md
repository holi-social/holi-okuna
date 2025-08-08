# Facebook Authentication with Ory Kratos

This document explains how to implement Facebook Sign In for your mobile app using the Okuna backend with Ory Kratos.

## Overview

The implementation allows mobile apps to authenticate users using Facebook access tokens. The backend verifies the token with Facebook, checks if the user exists in Ory Kratos, creates new users if needed, and returns a JWT ID token for the mobile app.

## GraphQL Mutation

### `authenticateWithFacebook`

**Input:**
```graphql
input FacebookAuthInput {
  accessToken: String!
}
```

**Response:**
```graphql
type FacebookAuthResult {
  success: Boolean!
  idToken: String
  userId: String
  email: String
  errorMessage: String
}
```

## Usage Example

### 1. Mobile App Flow

1. **Get Facebook Access Token**: Use Facebook SDK to get an access token from the user
2. **Call GraphQL Mutation**: Send the access token to the backend

```graphql
mutation AuthenticateWithFacebook($input: FacebookAuthInput!) {
  authenticateWithFacebook(input: $input) {
    success
    idToken
    userId
    email
    errorMessage
  }
}
```

**Variables:**
```json
{
  "input": {
    "accessToken": "facebook_access_token_here"
  }
}
```

### 2. Backend Process

The backend will:

1. **Verify Facebook Token**: Call Facebook Graph API to validate the access token and get user information
2. **Check Ory User**: Search for existing user in Ory Kratos with the Facebook ID
3. **Create User (if needed)**: If user doesn't exist, create a new user in Ory Kratos
4. **Generate ID Token**: Create a JWT token for the mobile app
5. **Return Response**: Send back the authentication result

### 3. Response Examples

**Success (New User):**
```json
{
  "data": {
    "authenticateWithFacebook": {
      "success": true,
      "idToken": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
      "userId": "ory-user-id",
      "email": "user@example.com",
      "errorMessage": null
    }
  }
}
```

**Success (Existing User):**
```json
{
  "data": {
    "authenticateWithFacebook": {
      "success": true,
      "idToken": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
      "userId": "existing-ory-user-id",
      "email": "user@example.com",
      "errorMessage": null
    }
  }
}
```

**Error:**
```json
{
  "data": {
    "authenticateWithFacebook": {
      "success": false,
      "idToken": null,
      "userId": null,
      "email": null,
      "errorMessage": "Invalid Facebook access token"
    }
  }
}
```

## Configuration

### Environment Variables

Make sure these environment variables are set:

- `ORY_BASE_URL`: URL of your Ory Kratos instance
- `ORY_ACCESS_TOKEN`: Admin access token for Ory Kratos
- `JWT_ALGORITHM`: JWT signing algorithm (default: HS256)
- `SECRET_KEY`: Django secret key for JWT signing

### Ory Kratos Setup

Ensure your Ory Kratos instance is configured to support Facebook OAuth:

1. Configure Facebook as an OAuth provider in your Ory Kratos configuration
2. Set up the appropriate redirect URLs
3. Configure the Facebook App ID and secret

## Security Considerations

1. **Token Validation**: The backend validates Facebook access tokens with Facebook's Graph API
2. **JWT Tokens**: ID tokens are signed with your application's secret key
3. **User Creation**: New users are created with verified email addresses
4. **Error Handling**: Proper error messages are returned for debugging

## Error Handling

Common error scenarios:

- **Invalid Facebook Token**: Token is expired or invalid
- **Missing Email**: Facebook user doesn't have an email address
- **Ory API Errors**: Issues with Ory Kratos admin API
- **Network Errors**: Connection issues with Facebook or Ory APIs

## Testing

Run the test suite to verify the implementation:

```bash
python manage.py test openbook_auth.tests.test_facebook_auth
```

## Mobile App Integration

After receiving the ID token:

1. **Store the token**: Securely store the JWT token on the device
2. **Include in requests**: Send the token in the Authorization header for subsequent API calls
3. **Token refresh**: Implement token refresh logic when tokens expire (24 hours)

## Example Mobile App Code (React Native)

```javascript
import { graphql } from 'react-apollo';
import { gql } from 'apollo-boost';

const AUTHENTICATE_WITH_FACEBOOK = gql`
  mutation AuthenticateWithFacebook($input: FacebookAuthInput!) {
    authenticateWithFacebook(input: $input) {
      success
      idToken
      userId
      email
      errorMessage
    }
  }
`;

const authenticateWithFacebook = async (accessToken) => {
  try {
    const { data } = await client.mutate({
      mutation: AUTHENTICATE_WITH_FACEBOOK,
      variables: {
        input: {
          accessToken: accessToken
        }
      }
    });

    const result = data.authenticateWithFacebook;
    
    if (result.success) {
      // Store the token securely
      await SecureStore.setItemAsync('idToken', result.idToken);
      return result;
    } else {
      throw new Error(result.errorMessage);
    }
  } catch (error) {
    console.error('Facebook authentication failed:', error);
    throw error;
  }
};
``` 