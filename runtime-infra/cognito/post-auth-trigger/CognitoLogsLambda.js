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
    console.log("Cognito Trigger Event:", JSON.stringify(event, null, 2));

    try {
        const bucketName = process.env.BucketName;
        const rolesTable = process.env.USER_ROLES_TABLE;
        const userPoolId = event.userPoolId;
        const userAttributes = event.request.userAttributes;
        const email = userAttributes.email;
        const userName = userAttributes.sub;
        const fileName = `${userName}.json`;

        console.log(`Processing user: ${email} (Sub: ${userName})`);

        // 1. Audit Log su S3 (Parallelo)
        const auditPromise = (async () => {
            console.log(`Checking audit log for ${fileName} in S3...`);
            const dataStr = JSON.stringify(userAttributes);
            const md5Hash = await getMD5HashFromFile(dataStr);
            const exists = await checkIfUserExists(s3Client, bucketName, fileName);
            
            if (!exists) {
                console.log(`Writing new audit log to S3 for ${email}`);
                await putObjectToS3(s3Client, bucketName, fileName, Buffer.from(dataStr), md5Hash);
            } else {
                console.log(`Audit log for ${email} already exists in S3.`);
            }
        })();

        // 2. Sincronizzazione Ruoli (DynamoDB -> Cognito)
        if (email && rolesTable && userPoolId) {
            await syncUserRoles(dbClient, cognitoClient, {
                email,
                roles_table: rolesTable,
                userPoolId,
                userName: event.userName,
                event
                
            });
        }

        await auditPromise;
    } catch (err) {
        console.error("Handler error:", err);
    }

    return event;
};