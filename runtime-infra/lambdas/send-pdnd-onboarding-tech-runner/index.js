import {
    executeAutomation,
    exposePrivateKey,
    publishWarningReport,
    storeReport,
} from './runtime.js';
import { buildOnboardingReport } from './onboarding-report.js';

const EVENT_NAME = 'onboarding-tech';

async function configureRuntime({ invocationRoot, secret }) {
    await exposePrivateKey(invocationRoot, secret);
}

export async function handler(event = {}, context = {}) {
    return executeAutomation({
        projectDirectory: 'Send_PDND_OnboardingTech_V3',
        event,
        configureRuntime,
        handleResult: async (result) => {
            const report = buildOnboardingReport(result);
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
