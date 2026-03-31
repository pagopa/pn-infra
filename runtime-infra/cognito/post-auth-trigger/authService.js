import { GetItemCommand } from "@aws-sdk/client-dynamodb";
import { AdminUpdateUserAttributesCommand } from "@aws-sdk/client-cognito-identity-provider";

export const syncUserRoles = async (dbClient, cognitoClient, params) => {
    const { email, roles_table, userPoolId, userName, event, expectedIdpId } = params;
    
    try {
        const dbRes = await dbClient.send(new GetItemCommand({
            TableName: roles_table,
            Key: { email: { S: email } }
        }));

        if (dbRes.Item && dbRes.Item.backoffice_tags) {
            const tags = dbRes.Item.backoffice_tags.S;
            const dbExpectedIdpId = dbRes.Item.expected_idpid ? dbRes.Item.expected_idpid.S : expectedIdpId;
            
            let issuerVerified = true;
            if (dbExpectedIdpId) {
                const identitiesStr = event.request.userAttributes.identities || "";
                if (!identitiesStr.includes(dbExpectedIdpId)) {
                    console.warn(`Security ALERT: User ${email} attempted login with wrong IdPID.`);
                    issuerVerified = false;
                }
            }

            if (issuerVerified) {
                await cognitoClient.send(new AdminUpdateUserAttributesCommand({
                    UserPoolId: userPoolId,
                    Username: userName,
                    UserAttributes: [
                        { Name: 'custom:backoffice_tags', Value: tags },
                        { Name: 'email_verified', Value: 'true' }
                    ]
                }));
                console.log(`Updated roles for ${email}`);
            }
        }
    } catch (err) {
        console.error("Error in role synchronization:", err);
    }
};
