import { GetItemCommand } from "@aws-sdk/client-dynamodb";
import { AdminUpdateUserAttributesCommand } from "@aws-sdk/client-cognito-identity-provider";
import { auditLog } from "./log.js";

export const syncUserRoles = async (dbClient, cognitoClient, params) => {
    const { email, roles_table, userPoolId, userName, event, expectedIdpId, envType } = params;
    const isDebug = process.env.LOG_LEVEL === 'DEBUG';
    const aud_orig = envType;
    const aud_type = "AUD_HD_LOGIN";
    
    // auditLog replaces console.log to avoid ingestion errors
    
    // AUDIT LOG: BEFORE
    auditLog(`BEFORE - Start syncUserRoles - sub=${userName}`, aud_type, aud_orig, userName);

    try {
        const dbRes = await dbClient.send(new GetItemCommand({
            TableName: roles_table,
            Key: { email: { S: email } }
        }));

        if (isDebug) {
            console.log(`DEBUG: DynamoDB response for sub=${userName}`, JSON.stringify(dbRes.Item));
        }

        if (dbRes.Item && dbRes.Item.backoffice_tags) {
            const tags = dbRes.Item.backoffice_tags.S;
            const dbExpectedIdpId = dbRes.Item.expected_idpid ? dbRes.Item.expected_idpid.S : expectedIdpId;
            
            console.log(`Found roles for sub=${userName}: ${tags}`);

            let issuerVerified = true;
            if (dbExpectedIdpId) {
                const identitiesStr = (event.request.userAttributes && event.request.userAttributes.identities) || "";
                if (!identitiesStr.includes(dbExpectedIdpId)) {
                    console.warn(`SECURITY ALERT: User with sub=${userName} attempted login with wrong IdPID`);
                    issuerVerified = false;
                }
            }

            if (issuerVerified) {
                // 1. DATABASE UPDATE (for Amplify SDK reading from user)
                console.log(`Updating Cognito DB for user sub=${userName} with tags: ${tags}`);
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
                
                // AUDIT LOG: AFTER (login successful)
                auditLog(`AFTER - User logged in and roles synchronized - sub=${userName} roles=${tags}`, aud_type, aud_orig, userName);
            }
        } else {
            // DEPROVISIONING: User not in DynamoDB (or no tags)
            console.warn(`DEPROVISIONING: User with sub=${userName} not found in DynamoDB. Stripping all roles`);

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

            // User not in DB - no audit log, just operational log
            console.warn(`User not found in DynamoDB roles table - sub=${userName}`);
        }
        
        return event;
    } catch (err) {
        // Critical exception - operational log only
        console.error(`Exception during syncUserRoles: ${err.message}`);

        console.error("Error in syncUserRoles:", err);
        throw err;
    }
};
