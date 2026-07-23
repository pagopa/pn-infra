import { randomUUID } from 'node:crypto';
import { createWriteStream } from 'node:fs';
import { mkdir, mkdtemp, readFile, rm, symlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { basename, dirname, join, normalize, resolve, sep } from 'node:path';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { pathToFileURL } from 'node:url';
import { GetObjectCommand, PutObjectCommand, S3Client } from '@aws-sdk/client-s3';
import { GetSecretValueCommand, SecretsManagerClient } from '@aws-sdk/client-secrets-manager';
import { PublishCommand, SNSClient } from '@aws-sdk/client-sns';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';
import unzipper from 'unzipper';

const secretsManager = new SecretsManagerClient({});
const s3 = new S3Client({});
const sns = new SNSClient({});

function required(name) {
    const value = process.env[name]?.trim();
    if (!value) {
        throw new Error(`Missing required environment variable: ${name}`);
    }
    return value;
}

async function readSecret(secretId) {
    const response = await secretsManager.send(new GetSecretValueCommand({ SecretId: secretId }));
    if (!response.SecretString) {
        throw new Error(`Secret ${secretId} does not contain SecretString`);
    }
    return response.SecretString;
}

function githubToken(secretValue) {
    try {
        const parsed = JSON.parse(secretValue);
        if (typeof parsed === 'string') {
            return parsed;
        }
        return parsed.token || parsed.githubToken || parsed.github_token;
    } catch (error) {
        if (error instanceof SyntaxError) {
            return secretValue;
        }
        throw error;
    }
}

async function downloadRepositoryArchive(destination) {
    const token = githubToken(await readSecret(required('GITHUB_TOKEN_SECRET_ID')));
    if (!token) {
        throw new Error('GitHub token secret does not contain a supported token value');
    }
    const repository = required('GITHUB_REPOSITORY');
    const ref = required('GITHUB_REF');
    const response = await fetch(
        `https://api.github.com/repos/${repository}/zipball/${encodeURIComponent(ref)}`,
        {
            headers: {
                Accept: 'application/vnd.github+json',
                Authorization: `Bearer ${token}`,
                'User-Agent': 'send-pdnd-automation-lambda',
                'X-GitHub-Api-Version': '2022-11-28',
            },
            redirect: 'follow',
        }
    );
    if (!response.ok || !response.body) {
        throw new Error(`GitHub archive download failed: HTTP ${response.status}`);
    }
    await pipeline(Readable.fromWeb(response.body), createWriteStream(destination, { mode: 0o600 }));
}

function safeArchivePath(root, entryPath) {
    const target = resolve(root, normalize(entryPath));
    if (target !== root && !target.startsWith(`${root}${sep}`)) {
        throw new Error(`Unsafe path in repository archive: ${entryPath}`);
    }
    return target;
}

async function extractProject(archivePath, projectName, destination) {
    const archive = await unzipper.Open.file(archivePath);
    const marker = `/${projectName}/`;
    let extractedFiles = 0;

    for (const entry of archive.files) {
        const markerIndex = entry.path.indexOf(marker);
        if (markerIndex < 0 || entry.type !== 'File') {
            continue;
        }
        const projectRelativePath = entry.path.slice(markerIndex + marker.length);
        if (!projectRelativePath) {
            continue;
        }
        const target = safeArchivePath(destination, projectRelativePath);
        await mkdir(dirname(target), { recursive: true });
        await pipeline(entry.stream(), createWriteStream(target, { mode: 0o600 }));
        extractedFiles += 1;
    }
    if (extractedFiles === 0) {
        throw new Error(`Project ${projectName} was not found in pn-troubleshooting archive`);
    }
}

function csvValue(value) {
    return `"${String(value ?? '').replaceAll('"', '""')}"`;
}

function signupCsv(report) {
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

function reportMetadata(automation, result) {
    if (automation === 'signup') {
        const pending = result.pendingAgreementsSummary || {};
        return {
            title: 'Automazione attivazioni PDND SEND',
            filename: 'send-pdnd-signup.csv',
            csv: signupCsv(result),
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

async function storeAndNotifyReport(automation, result, context) {
    const metadata = reportMetadata(automation, result);
    const body = metadata.reportPath
        ? await readFile(metadata.reportPath)
        : Buffer.from(metadata.csv, 'utf8');
    const now = new Date();
    const datePath = now.toISOString().slice(0, 10).replaceAll('-', '/');
    const bucket = required('REPORT_BUCKET');
    const prefix = required('REPORT_PREFIX').replace(/^\/+|\/+$/g, '');
    const key = `${prefix}/${datePath}/${now.toISOString().replaceAll(':', '-')}-${metadata.filename}`;

    await s3.send(new PutObjectCommand({
        Bucket: bucket,
        Key: key,
        Body: body,
        ContentType: 'text/csv',
        ServerSideEncryption: 'AES256',
    }));
    const expiresIn = Number(process.env.REPORT_URL_EXPIRATION_SECONDS || 3600);
    const downloadUrl = await getSignedUrl(
        s3,
        new GetObjectCommand({ Bucket: bucket, Key: key }),
        { expiresIn }
    );
    const producer = required('REPORT_PRODUCER');
    const message = {
        schemaVersion: '1.0',
        eventId: context.awsRequestId || randomUUID(),
        eventType: 'report',
        producer,
        eventName: automation,
        occurredAt: now.toISOString(),
        severity: 'info',
        environment: process.env.ENVIRONMENT_TYPE,
        title: metadata.title,
        data: {
            metrics: metadata.metrics,
            durationMs: result.durationMs,
        },
        links: { report: `s3://${bucket}/${key}` },
        attachment: {
            filename: metadata.filename,
            contentType: 'text/csv',
            size: body.length,
            downloadUrl,
        },
    };
    await sns.send(new PublishCommand({
        TopicArn: required('WARNING_SNS_TOPIC_ARN'),
        Subject: `[${process.env.ENVIRONMENT_TYPE}] ${metadata.title}`.slice(0, 100),
        Message: JSON.stringify(message),
    }));
    return { bucket, key, metrics: metadata.metrics };
}

async function loadAutomation() {
    const invocationRoot = await mkdtemp(join(tmpdir(), 'send-pdnd-'));
    try {
        const archivePath = join(invocationRoot, 'repository.zip');
        const projectRoot = join(invocationRoot, 'project');
        await mkdir(projectRoot, { recursive: true, mode: 0o700 });
        await downloadRepositoryArchive(archivePath);
        await extractProject(archivePath, required('PROJECT_DIRECTORY'), projectRoot);
        await rm(archivePath, { force: true });
        await symlink('/var/task/node_modules', join(projectRoot, 'node_modules'), 'dir');
        const module = await import(`${pathToFileURL(join(projectRoot, 'lambda.js')).href}?${randomUUID()}`);
        if (typeof module.handler !== 'function') {
            throw new Error('Downloaded project does not export lambda.handler');
        }
        return { handler: module.handler, invocationRoot };
    } catch (error) {
        await rm(invocationRoot, { recursive: true, force: true });
        throw error;
    }
}

export async function handler(event = {}, context = {}) {
    const automation = required('AUTOMATION_NAME');
    const { handler: automationHandler, invocationRoot } = await loadAutomation();
    try {
        const result = await automationHandler(event);
        const report = await storeAndNotifyReport(automation, result, context);
        console.log(JSON.stringify({ message: 'Automation completed', automation, report }));
        return { automation, report };
    } finally {
        await rm(invocationRoot, { recursive: true, force: true });
    }
}
