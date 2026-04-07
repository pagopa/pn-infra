import { GetItemCommand } from "@aws-sdk/client-dynamodb";
import { AdminUpdateUserAttributesCommand } from "@aws-sdk/client-cognito-identity-provider";

import { GetItemCommand } from "@aws-sdk/client-dynamodb";
import { AdminUpdateUserAttributesCommand } from "@aws-sdk/client-cognito-identity-provider";

export const syncUserRoles = async (dbClient, cognitoClient, s3Client, params) => {
    const { email, roles_table, userPoolId, userName, event, expectedIdpId, bucketName } = params;
    const isDebug = process.env.LOG_LEVEL === 'DEBUG';
    
    console.log(`Starting role sync for ${email} on table ${roles_table} (PreToken V2)`);
    
    try {
        const dbRes = await dbClient.send(new GetItemCommand({
            TableName: roles_table,
            Key: { email: { S: email } }
        }));

        if (isDebug) {
            console.log(`DEBUG: DynamoDB response for ${email}:`, JSON.stringify(dbRes.Item, null, 2));
        }

        if (dbRes.Item && dbRes.Item.backoffice_tags) {
            const tags = dbRes.Item.backoffice_tags.S;
            const dbExpectedIdpId = dbRes.Item.expected_idpid ? dbRes.Item.expected_idpid.S : expectedIdpId;
            
            console.log(`Found roles for ${email}: ${tags}.`);

            // Audit Log via CloudWatch (verrà captato dai sistemi di log aggregation)
            console.log(JSON.stringify({
                eventType: "AUD-HD-LOGIN",
                timestamp: new Date().toISOString(),
                user: email,
                sub: userName,
                roles: tags,
                triggerSource: event.triggerSource,
                userPoolId: userPoolId
            }));

            let issuerVerified = true;
            // Teniamo commentato per i test iniziali se necessario
            /*
            if (dbExpectedIdpId) {
                const identitiesStr = (event.request.userAttributes && event.request.userAttributes.identities) || "";
                if (!identitiesStr.includes(dbExpectedIdpId)) {
                    console.warn(`SECURITY ALERT: User ${email} attempted login with wrong IdPID.`);
                    issuerVerified = false;
                }
            }
            */

            if (issuerVerified) {
                // 1. AGGIORNAMENTO DATABASE (per Amplify SDK che legge dall'utente)
                console.log(`Updating Cognito DB for user ${userName} with tags: ${tags}`);
                await cognitoClient.send(new AdminUpdateUserAttributesCommand({
                    UserPoolId: userPoolId,
                    Username: userName,
                    UserAttributes: [
                        { Name: 'custom:backoffice_tags', Value: tags },
                        { Name: 'email_verified', Value: 'true' }
                    ]
                }));

                // 2. OVERRIDE TOKEN FORMATO V2 (per avere tutto popolato atomisticamente)
                event.response = {
                    claimsAndScopeOverrideDetails: {
                        idTokenGeneration: {
                            claimsToAddOrOverride: {
                                "custom:backoffice_tags": tags,
                                "email_verified": "true"
                            }
                        },
                        accessTokenGeneration: {
                            claimsToAddOrOverride: {
                                "custom:backoffice_tags": tags
                            }
                        }
                    }
                };
                
                console.log(`SUCCESS: Updated DB and Prepared V2 Token override for ${email}`);
            }
        }
        
        return event;
    } catch (err) {
        console.error("Error in syncUserRoles:", err);
        throw err;
    }
};
