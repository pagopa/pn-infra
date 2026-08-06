function csvValue(value) {
    const text = String(value ?? '');
    return `"${text.replaceAll('"', '""')}"`;
}

function createCsv(report) {
    const header = [
        'category', 'id', 'consumerId', 'tenant', 'tenantKind', 'title',
        'eService', 'institution', 'reason', 'note',
    ];
    const sections = [
        ['agreementsToReview', report.agreementsToReview],
        ['agreementsActivated', report.agreementsActivated],
        ['agreementsNotActivated', report.agreementsNotActivated],
        ['purposesActivated', report.purposesActivated],
        ['purposesNotActivated', report.purposesNotActivated],
    ];
    const rows = [header];

    for (const [category, items] of sections) {
        for (const item of items || []) {
            rows.push([
                category,
                item.id,
                item.consumerId,
                item.tenantName,
                item.tenantKind,
                item.title,
                item.eserviceName && `${item.eserviceName} [${item.eserviceId}]`,
                item.institution,
                item.reason,
                item.metadataError,
            ]);
        }
    }
    return `${rows.map(row => row.map(csvValue).join(',')).join('\n')}\n`;
}

export function buildSignupReport(result) {
    const pending = result.pendingAgreementsSummary || {};
    return {
        title: 'Automazione attivazioni PDND SEND',
        filename: 'send-pdnd-signup.csv',
        csv: createCsv(result),
        metrics: {
            'Accordi pending': pending.producerTotal || 0,
            'Accordi SEND': pending.sendTotal || 0,
            'Da verificare': pending.toReviewTotal || 0,
            'Fruizioni attivate': result.agreementsActivated?.length || 0,
            'Fruizioni non attivate': result.agreementsNotActivated?.length || 0,
            'Finalita attivate': result.purposesActivated?.length || 0,
            'Finalita non attivate': result.purposesNotActivated?.length || 0,
        },
    };
}
