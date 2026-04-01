import { S3Client } from "@aws-sdk/client-s3";
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { putObjectToS3, checkIfUserExists, getMD5HashFromFile } from './utils.js';
import { syncUserRoles } from './authService.js';

const s3Client = new S3Client();
const dbClient = new DynamoDBClient();

export const handler = async (event) => {
    if (!event) return event;
    const triggerSource = event.triggerSource;
    console.log(`Cognito Trigger [${triggerSource}] Event:`, JSON.stringify(event, null, 2));

    try {
        const bucketName = process.env.BucketName;
        const rolesTable = process.env.USER_ROLES_TABLE;
        const expectedIdpId = process.env.EXPECTED_IDPID;
        const userAttributes = event.request.userAttributes;
        const email = userAttributes.email;
        const userName = userAttributes.sub;
        const fileName = `${userName}.json`;

        // 1. Audit Log su S3 (Solo per PostAuthentication)
        if (triggerSource === 'PostAuthentication_Authentication') {
            console.log(`Writing Audit Log for ${email} to S3...`);
            try {
                const dataStr = JSON.stringify(userAttributes);
                const md5Hash = await getMD5HashFromFile(dataStr);
                const exists = await checkIfUserExists(s3Client, bucketName, fileName);
                
                if (!exists) {
                    await putObjectToS3(s3Client, bucketName, fileName, Buffer.from(dataStr), md5Hash);
                    console.log(`Audit Log for ${email} successfully written.`);
                } else {
                    console.log(`Audit Log for ${email} already exists.`);
                }
            } catch (s3Err) {
                console.error("S3 Audit Error:", s3Err);
            }
            return event;
        }

        // 2. Sincronizzazione Ruoli e Override dei Claims (Solo per PreTokenGeneration)
        if (triggerSource === 'PreTokenGeneration_Authentication') {
            console.log(`Processing Roles for ${email} (PreTokenGeneration)...`);
            if (email && rolesTable) {
                return await syncUserRoles(dbClient, {
                    email,
                    roles_table: rolesTable,
                    event,
                    expectedIdpId
                });
            }
        }

        return event;
    } catch (err) {
        console.error("Critical Error in Lambda Handler:", err);
        return event;
    }
};