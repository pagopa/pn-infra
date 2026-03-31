import { GetItemCommand } from "@aws-sdk/client-dynamodb";
import { AdminUpdateUserAttributesCommand } from "@aws-sdk/client-cognito-identity-provider";

export const syncUserRoles = async (dbClient, cognitoClient, params) => {
    const { email, roles_table, userPoolId, userName, event, expectedIdpId } = params;
    const isDebug = process.env.LOG_LEVEL === 'DEBUG';
    
    console.log(`Starting role sync for ${email} on table ${roles_table}`);
    
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
            
            console.log(`Found roles for ${email}: ${tags}. Expected IdPID: ${dbExpectedIdpId || 'Any'}`);

            let issuerVerified = true;
            if (dbExpectedIdpId) {
                const identitiesStr = event.request.userAttributes.identities || "";
                
                if (isDebug) {
                    console.log(`DEBUG: User identities string: ${identitiesStr}`);
                }

                if (!identitiesStr.includes(dbExpectedIdpId)) {
                    console.warn(`SECURITY ALERT: User ${email} attempted login with wrong IdPID. Identities: ${identitiesStr}`);
                    issuerVerified = false;
                } else {
                    console.log(`IdPID ${dbExpectedIdpId} verified for ${email}`);
                }
            }

            if (issuerVerified) {
                console.log(`Updating Cognito user ${userName} with tags: ${tags}`);
                await cognitoClient.send(new AdminUpdateUserAttributesCommand({
                    UserPoolId: userPoolId,
                    Username: userName,
                    UserAttributes: [
                        { Name: 'custom:backoffice_tags', Value: tags },
                        { Name: 'email_verified', Value: 'true' }
                    ]
                }));
                console.log(`SUCCESS: Updated roles and verified email for ${email}`);
            }
        } else {
            console.log(`No backoffice roles found in DynamoDB for user ${email}`);
        }
    } catch (err) {
        console.error("Error in syncUserRoles:", err);
        throw err;
    }
};
