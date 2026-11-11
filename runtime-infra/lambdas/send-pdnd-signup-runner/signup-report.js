function csvValue(value) {
    const text = String(value ?? '');
    return `"${text.replaceAll('"', '""')}"`;
}

function createCsv(report) {
    const header = [
        'category', 'id', 'consumerId', 'tenant', 'tenantKind', 'title',
        'eService', 'institution', 'reason', 'note',
        'categoryLabel',
    ];
    const sections = [
        ['agreementsToReview', report.agreementsToReview, 'Fruizioni generiche SEND da verificare'],
        ['agreementsActivated', report.agreementsActivated, 'Fruizioni con e-service SEND attivate'],
        ['agreementsNotActivated', report.agreementsNotActivated, 'Fruizioni con e-service SEND non attivate'],
        ['purposesActivated', report.purposesActivated, 'Finalita SEND attivate'],
        ['purposesNotActivated', report.purposesNotActivated, 'Finalita SEND non attivate'],
    ];
    const rows = [header];

    for (const [category, items, categoryLabel] of sections) {
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
                categoryLabel,
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
            'Tutte le fruizioni SEND pending': pending.producerTotal || 0,
            'Fruizioni con e-service SEND pending': pending.sendTotal || 0,
            'Fruizioni generiche SEND da verificare': pending.toReviewTotal || 0,
            'Fruizioni con e-service SEND attivate': result.agreementsActivated?.length || 0,
            'Fruizioni con e-service SEND non attivate': result.agreementsNotActivated?.length || 0,
            'Finalita SEND attivate': result.purposesActivated?.length || 0,
            'Finalita SEND non attivate': result.purposesNotActivated?.length || 0,
        },
        presentation: {
            format: 'slack-mrkdwn',
            body: '*Fruizioni da verificare*\n' +
                'Riguardano e-service diversi da quello SEND configurato e sono escluse ' +
                'dall\'approvazione automatica.\n' +
                '*Dettaglio enti nel CSV*\n' +
                'Include gli enti da verificare e gli esiti delle fruizioni e delle finalita, ' +
                'con identificativi, motivi delle mancate attivazioni e note sui metadati non disponibili.',
        },
    };
}
