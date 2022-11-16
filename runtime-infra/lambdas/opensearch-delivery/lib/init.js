import { Client } from '@opensearch-project/opensearch';
import { SecretsManagerClient, GetSecretValueCommand } from '@aws-sdk/client-secrets-manager';

const secretsManager = new SecretsManagerClient({ region: process.env.AWS_REGION });

async function getOpenSearchSecret() {
  const input = {
    SecretId: process.env.CLUSTER_SECRET_ARN,
  };

  const command = new GetSecretValueCommand(input);
  const response = await secretsManager.send(command);

  const secret = JSON.parse(response.SecretString);
  return secret;
}

async function initOpenSearchClient() {
  const credentials = await getOpenSearchSecret();

  const username = encodeURIComponent(credentials.username);
  const password = encodeURIComponent(credentials.password);
  const clusterAuth = `${username}:${password}`
  const clusterHost = process.env.CLUSTER_ENDPOINT.replace(/^http[s]?:\/\//, '');

  const openSearch = new Client({
    node: `https://${clusterAuth}@${clusterHost}`
  });

  return openSearch;
}

export { initOpenSearchClient };
