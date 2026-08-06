import {
    executeAutomation,
    exposePrivateKey,
    exposeSelfcareKey,
    publishWarningReport,
    storeReport,
} from './runtime.js';
import { buildSignupReport } from './signup-report.js';

const EVENT_NAME = 'signup';

async function configureRuntime({ invocationRoot, secret }) {
    await exposePrivateKey(invocationRoot, secret);
    exposeSelfcareKey(secret);
}

export async function handler(event = {}, context = {}) {
    return executeAutomation({
        projectDirectory: 'Send_PDND_SignUP_V3',
        event: {
            ...event,
            dryRun: event.dryRun === true || process.env.SIGNUP_DRY_RUN === 'true',
        },
        configureRuntime,
        handleResult: async (result) => {
            const report = buildSignupReport(result);
            const storedReport = await storeReport(report);
            const notification = await publishWarningReport({
                eventName: EVENT_NAME,
                report,
                storedReport,
                durationMs: result.durationMs,
                context,
            });
            console.log(JSON.stringify({
                message: 'Automation completed',
                eventName: EVENT_NAME,
                report: notification,
            }));
            return { automation: EVENT_NAME, report: notification };
        },
    });
}
