import { S3Client, PutObjectCommand, HeadObjectCommand } from "@aws-sdk/client-s3";
import { DynamoDBClient, GetItemCommand } from "@aws-sdk/client-dynamodb";
import { CognitoIdentityProviderClient, AdminUpdateUserAttributesCommand } from "@aws-sdk/client-cognito-identity-provider";
import md5 from 'crypto-js';

import { S3Client, PutObjectCommand, HeadObjectCommand } from "@aws-sdk/client-s3";
import { DynamoDBClient, GetItemCommand } from "@aws-sdk/client-dynamodb";
import { CognitoIdentityProviderClient, AdminUpdateUserAttributesCommand } from "@aws-sdk/client-cognito-identity-provider";
import md5 from 'crypto-js';

const s3Client = new S3Client();
const dbClient = new DynamoDBClient();
const cognitoClient = new CognitoIdentityProviderClient();

export const handler = async(event) => {
    if(event) {
        try {
            const bucket_name = process.env.BucketName;
            const roles_table = process.env.USER_ROLES_TABLE;
            const userPoolId = event.userPoolId;

            const userAttributeJson =  event.request.userAttributes;
            const email = userAttributeJson.email;
            const userName = userAttributeJson.sub;
            const fileName = userName + '.json';

            console.log("Processing user:", email);

            // 1. S3 Logging (in parallelo)
            const s3Promise = (async () => {
                var buf = Buffer.from(JSON.stringify(userAttributeJson));
                var md5File = buf.toString();
                var md5Hash = await getMD5HashFromFile(md5File);
                if(await checkIfUserexists(s3Client ,bucket_name, fileName) === false) {
                    await putObjectToS3(s3Client, bucket_name, fileName, buf, md5Hash);
                }
            })();

            // 2. Ruoli da DynamoDB e aggiornamento Cognito (nuovo per Google/SAML)
            if (email && roles_table && userPoolId) {
                try {
                    const dbRes = await dbClient.send(new GetItemCommand({
                        TableName: roles_table,
                        Key: { email: { S: email } }
                    }));

                    if (dbRes.Item && dbRes.Item.backoffice_tags) {
                        const tags = dbRes.Item.backoffice_tags.S;
                        const expectedIdpId = dbRes.Item.expected_idpid ? dbRes.Item.expected_idpid.S : null;
                        
                        // 3. Validazione dell'IdPID (Security Check)
                        let issuerVerified = true;
                        if (expectedIdpId) {
                            const identitiesStr = userAttributeJson.identities || "";
                            if (!identitiesStr.includes(expectedIdpId)) {
                                console.warn(`Security ALERT: User ${email} attempted login with wrong IdPID.`);
                                issuerVerified = false;
                            }
                        }

                        if (issuerVerified) {
                            await cognitoClient.send(new AdminUpdateUserAttributesCommand({
                                UserPoolId: userPoolId,
                                Username: event.userName,
                                UserAttributes: [
                                    {
                                        Name: 'custom:backoffice_tags',
                                        Value: tags
                                    },
                                    {
                                        Name: 'email_verified',
                                        Value: 'true'
                                    }
                                ]
                            }));
                        }
                    }
                } catch (dbErr) {
                    console.error("Error in DynamoDB/Cognito update flow:", dbErr);
                }
            }
            
            // Attendiamo S3 prima di chiudere
            await s3Promise;
        }
        catch(err) {
            console.log(err);
        }
    }
    
    return event;
};

const putObjectToS3 = async (s3Client ,bucket, key, data, md5Hash) => {
    var params = {
        Bucket : bucket,
        Key : key,
        Body : data,
        ContentMD5: md5Hash
    };
    
    try {
        await s3Client.send(new PutObjectCommand(params));
        console.log("Successfully written to S3");
    }
    catch(err) {
        console.log("Error occured in put object: ", err);
    }
};

const checkIfUserexists = async (s3Client, bucket, key) => {
    var params = {
        Bucket: bucket,
        Key: key
    };
    var returnValue;
    await s3Client.send(new HeadObjectCommand(params))
        .then((data) => { //file exists - don't write
            returnValue = true;
        })
        .catch((err) => {
            if(err.name === 'NotFound') { //File does not exist
                returnValue = false;
            }
            else if(err.name === 403|| err.message === 'UnknownError') { 
                returnValue = true;
            }
        });
    return returnValue;
};

const getMD5HashFromFile = async (file) => {
    var hash = md5.MD5(file);
    var base64Hash = hash.toString(md5.enc.Base64);
    return base64Hash;
};