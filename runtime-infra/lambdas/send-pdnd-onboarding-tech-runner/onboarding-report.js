import { basename } from 'node:path';

export function buildOnboardingReport(result) {
    const summary = result.summary || {};
    return {
        title: 'Report onboarding tecnico PDND SEND',
        filename: basename(result.reportPath || 'out-onBoardingTech.csv'),
        reportPath: result.reportPath,
        metrics: {
            'Enti PN analizzati': summary.onboardInstitutions || 0,
            'Finalita SEND attive': summary.activePurposes || 0,
            'Tenant IPA attivi': summary.activePurposeTenants || 0,
            'Enti con onboarding tecnico': summary.technicalOnboardingInstitutions || 0,
            'Finalita senza tenant IPA': summary.purposesWithoutTenant || 0,
        },
    };
}
