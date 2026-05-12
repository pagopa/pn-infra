import { S3Client } from "@aws-sdk/client-s3";
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { CognitoIdentityProviderClient } from "@aws-sdk/client-cognito-identity-provider";
import { putObjectToS3, checkIfUserExists, getMD5HashFromFile } from './utils.js';
import { syncUserRoles } from './authService.js';

const s3Client = new S3Client();
const dbClient = new DynamoDBClient();
const cognitoClient = new CognitoIdentityProviderClient();

export const handler = async (event) => {
    if (!event) return event;
    const triggerSource = event.triggerSource;
    // Log deactivated to prevent OpenSearch ingestion errors
    // console.log(`Cognito Trigger [${triggerSource}] Event:`, JSON.stringify(event, null, 2));

    try {
        const bucketName = process.env.BucketName;
        const rolesTable = process.env.USER_ROLES_TABLE;
        const expectedIdpId = process.env.EXPECTED_IDPID;
        const envType = process.env.ENVIRONMENT_TYPE;
        const userAttributes = event.request.userAttributes;
        const email = userAttributes.email;
        const userName = userAttributes.sub;
        const userPoolId = event.userPoolId;

        // 1. SSO Login e Ruoli (su authService.js)
        if (triggerSource === 'TokenGeneration_HostedAuth') {
            await syncUserRoles(dbClient, cognitoClient, {
                email,
                roles_table: rolesTable,
                userPoolId,
                userName,
                event,
                expectedIdpId,
                envType
            });
            // NOTA: Gli audit log standard (AUDIT10Y) sono emessi dentro syncUserRoles
            return event;
        }

        // 2. Login locale (utenza Cognito diretta) + Salvataggio su S3
        if (triggerSource === 'PostAuthentication_Authentication') {
            console.warn(`LOCAL_USER_LOGIN_DETECTED - User ${email} (sub=${userName}) logged in with local Cognito credentials`);
            try {
                const fileName = `${userName}.json`;
                const dataStr = JSON.stringify(userAttributes);
                const md5Hash = await getMD5HashFromFile(dataStr);
                const exists = await checkIfUserExists(s3Client, bucketName, fileName);
                
                if (!exists) {
                    console.log(`S3 Backup: Saving user attributes for ${userName}`);
                    await putObjectToS3(s3Client, bucketName, fileName, Buffer.from(dataStr), md5Hash);
                }
            } catch (s3Err) {
                console.error("S3 Backup Error:", s3Err);
            }
            return event;
        }

        return event;
    } catch (err) {
        console.error("Critical Error in Lambda Handler:", err);
        return event;
    }
};