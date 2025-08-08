# Facebook Authentication with Ory Kratos

This document explains how to implement Facebook Sign In for your mobile app using the Okuna backend with Ory Kratos.

## Overview

The implementation allows mobile apps to authenticate users using Facebook access tokens. The backend verifies the token with Facebook, finds or creates a user in Ory Kratos, creates a Kratos session, and returns the session token for the mobile app.

## Authentication Flow

1. **Verify Facebook Access Token**: Call Facebook Graph API to validate the access token and get user information
2. **Find or Create Kratos Identity**: Search for existing user in Ory Kratos with the Facebook ID, or create a new identity
3. **Create Kratos Session**: Create an admin session for the identity using Ory Kratos Admin API
4. **Return Session Token**: Send back the Kratos session token to the mobile client

## GraphQL Mutation

### `authenticateWithFacebook`

**Input:**
```graphql
input FacebookAuthInput {
  accessToken: String!
  provider: String!
}
```

**Response:**
```graphql
type FacebookAuthResult {
  success: Boolean!
  sessionToken: String
  userId: String
  email: String
  errorMessage: String
}
```

## Usage Example

### 1. Mobile App Flow

1. **Get Facebook Access Token**: Use Facebook SDK to get an access token from the user
2. **Call GraphQL Mutation**: Send the access token and provider to the backend

```graphql
mutation AuthenticateWithFacebook($input: FacebookAuthInput!) {
  authenticateWithFacebook(input: $input) {
    success
    sessionToken
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
    "accessToken": "facebook_access_token_here",
    "provider": "facebook-123"
  }
}
```

### 2. Backend Process

The backend will:

1. **Verify Facebook Token**: Call Facebook Graph API to validate the access token and get user information
2. **Find or Create Kratos Identity**: Search for existing user in Ory Kratos with the Facebook ID, or create a new identity
3. **Create Kratos Session**: Create an admin session for the identity using Ory Kratos Admin API
4. **Return Session Token**: Send back the Kratos session token

### 3. Response Examples

**Success (New User):**
```json
{
  "data": {
    "authenticateWithFacebook": {
      "success": true,
      "sessionToken": "ory-session-token-here",
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
      "sessionToken": "ory-session-token-here",
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
      "sessionToken": null,
      "userId": null,
      "email": null,
      "errorMessage": "Authentication failed"
    }
  }
}
```

## Configuration

### Environment Variables

Make sure these environment variables are set:

- `ORY_BASE_URL`: URL of your Ory Kratos instance
- `ORY_ACCESS_TOKEN`: Admin access token for Ory Kratos

### Ory Kratos Setup

Ensure your Ory Kratos instance is configured to support Facebook OAuth:

1. Configure Facebook as an OAuth provider in your Ory Kratos configuration
2. Set up the appropriate redirect URLs
3. Configure the Facebook App ID and secret

## Security Considerations

1. **Token Validation**: The backend validates Facebook access tokens with Facebook's Graph API
2. **Kratos Sessions**: Session tokens are managed by Ory Kratos and provide secure authentication
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

After receiving the session token:

1. **Store the token**: Securely store the Kratos session token on the device
2. **Include in requests**: Send the token in the Authorization header for subsequent API calls
3. **Session management**: The session is managed by Ory Kratos and will expire according to Kratos configuration

## Example Mobile App Code (React Native)

```javascript
import { graphql } from 'react-apollo';
import { gql } from 'apollo-boost';

const AUTHENTICATE_WITH_FACEBOOK = gql`
  mutation AuthenticateWithFacebook($input: FacebookAuthInput!) {
    authenticateWithFacebook(input: $input) {
      success
      sessionToken
      userId
      email
      errorMessage
    }
  }
`;

const authenticateWithFacebook = async (accessToken, provider) => {
  try {
    const { data } = await client.mutate({
      mutation: AUTHENTICATE_WITH_FACEBOOK,
      variables: {
        input: {
          accessToken: accessToken,
          provider: provider
        }
      }
    });

    const result = data.authenticateWithFacebook;
    
    if (result.success) {
      // Store the session token securely
      await SecureStore.setItemAsync('sessionToken', result.sessionToken);
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