import { GetItemCommand } from "@aws-sdk/client-dynamodb";
import { AdminUpdateUserAttributesCommand } from "@aws-sdk/client-cognito-identity-provider";
import { auditLog } from "./log.js";

export const syncUserRoles = async (dbClient, cognitoClient, params) => {
    const { email, roles_table, userPoolId, userName, event, expectedIdpId } = params;
    const isDebug = process.env.LOG_LEVEL === 'DEBUG';
    const aud_orig = "https://helpdesk.dev.notifichedigitali.it";
    const aud_type = "AUD_HD_LOGIN";
    
    console.log(`Starting role sync for ${email} on table ${roles_table} (PreToken V2)`);
    
    // AUDIT LOG: BEFORE
    auditLog("Start syncUserRoles", aud_type, aud_orig, "", "PF", "PF-" + userName, null, userName).info("info");

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

            let issuerVerified = true;
            // Keep commented for initial testing if needed
            if (dbExpectedIdpId) {
                const identitiesStr = (event.request.userAttributes && event.request.userAttributes.identities) || "";
                if (!identitiesStr.includes(dbExpectedIdpId)) {
                    console.warn(`SECURITY ALERT: User ${email} attempted login with wrong IdPID.`);
                    issuerVerified = false;
                }
            }

            if (issuerVerified) {
                // 1. DATABASE UPDATE (for Amplify SDK reading from user)
                console.log(`Updating Cognito DB for user ${userName} with tags: ${tags}`);
                await cognitoClient.send(new AdminUpdateUserAttributesCommand({
                    UserPoolId: userPoolId,
                    Username: userName,
                    UserAttributes: [
                        { Name: 'custom:backoffice_tags', Value: tags },
                        { Name: 'email_verified', Value: 'true' }
                    ]
                }));

                // 2. TOKEN OVERRIDE V2 FORMAT (atomic population)
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
                
                // AUDIT LOG: SUCCESS
                auditLog("User logged in and roles synchronized", aud_type, aud_orig, "OK", "PF", "PF-" + userName, null, userName).info("success");

                console.log(`SUCCESS: Updated DB and Prepared V2 Token override for ${email}`);
            }
        } else {
            // DEPROVISIONING: User not in DynamoDB (or no tags)
            console.warn(`DEPROVISIONING: User ${email} not found in DynamoDB. Stripping all roles.`);

            // 1. COGNITO DATABASE CLEANUP (security)
            await cognitoClient.send(new AdminUpdateUserAttributesCommand({
                UserPoolId: userPoolId,
                Username: userName,
                UserAttributes: [
                    { Name: 'custom:backoffice_tags', Value: "" }
                ]
            }));

            // 2. EMPTY TOKEN OVERRIDE (User logs in but has no permissions)
            event.response = {
                claimsAndScopeOverrideDetails: {
                    idTokenGeneration: {
                        claimsToAddOrOverride: {
                            "custom:backoffice_tags": ""
                        }
                    },
                    accessTokenGeneration: {
                        claimsToAddOrOverride: {
                            "custom:backoffice_tags": ""
                        }
                    }
                }
            };

            // AUDIT LOG: FAILURE (User not in DB)
            auditLog("User not found in DynamoDB roles table", aud_type, aud_orig, "KO", "PF", "PF-" + userName, null, userName).warn("error");
        }
        
        return event;
    } catch (err) {
        // AUDIT LOG: FAILURE (Critical Exception)
        auditLog(`Exception during syncUserRoles: ${err.message}`, aud_type, aud_orig, "KO", "PF", "PF-" + userName, null, userName).error("error");

        console.error("Error in syncUserRoles:", err);
        throw err;
    }
};
