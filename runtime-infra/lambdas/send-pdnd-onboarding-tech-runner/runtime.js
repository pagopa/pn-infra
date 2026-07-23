import { randomUUID } from 'node:crypto';
import { createWriteStream } from 'node:fs';
import {
    mkdir,
    mkdtemp,
    readFile,
    rm,
    symlink,
    writeFile,
} from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { basename, dirname, join, normalize, resolve, sep } from 'node:path';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { pathToFileURL } from 'node:url';
import { GetObjectCommand, PutObjectCommand, S3Client } from '@aws-sdk/client-s3';
import {
    GetSecretValueCommand,
    SecretsManagerClient,
} from '@aws-sdk/client-secrets-manager';
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

function parseJsonSecret(secretId, secretValue) {
    let secret;
    try {
        secret = JSON.parse(secretValue);
    } catch (error) {
        if (error instanceof SyntaxError) {
            throw new Error(`Secret ${secretId} must contain a JSON object`);
        }
        throw error;
    }
    if (!secret || typeof secret !== 'object' || Array.isArray(secret)) {
        throw new Error(`Secret ${secretId} must contain a JSON object`);
    }
    return secret;
}

function secretField(secretId, secret, field) {
    if (!secret[field]) {
        throw new Error(`Secret ${secretId} does not contain ${field}`);
    }
    return String(secret[field]);
}

async function readAutomationSecret() {
    const secretId = required('AUTOMATION_SECRET_ID');
    return {
        id: secretId,
        value: parseJsonSecret(secretId, await readSecret(secretId)),
    };
}

export async function exposePrivateKey(invocationRoot, secret) {
    const privateKeyPath = join(invocationRoot, 'pdnd-private-key.pem');
    await writeFile(
        privateKeyPath,
        secretField(secret.id, secret.value, 'pdnd_private_key'),
        {
            encoding: 'utf8',
            flag: 'wx',
            mode: 0o600,
        }
    );
    process.env.PRIVATE_KEY_PATH = privateKeyPath;
}

export function exposeSelfcareKey(secret) {
    process.env.SELFCARE_APIKEY = secretField(secret.id, secret.value, 'selfcare_key');
}

function clearAutomationSecrets() {
    delete process.env.PRIVATE_KEY_PATH;
    delete process.env.SELFCARE_APIKEY;
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

export async function executeAutomation({
    projectDirectory,
    event,
    configureRuntime,
    handleResult,
}) {
    const invocationRoot = await mkdtemp(join(tmpdir(), 'send-pdnd-'));
    try {
        const archivePath = join(invocationRoot, 'repository.zip');
        const projectRoot = join(invocationRoot, 'project');
        await mkdir(projectRoot, { recursive: true, mode: 0o700 });
        await downloadRepositoryArchive(archivePath);
        await extractProject(archivePath, projectDirectory, projectRoot);
        await rm(archivePath, { force: true });
        await symlink('/var/task/node_modules', join(projectRoot, 'node_modules'), 'dir');

        const secret = await readAutomationSecret();
        await configureRuntime({ invocationRoot, secret });

        const moduleUrl = `${pathToFileURL(join(projectRoot, 'lambda.js')).href}?${randomUUID()}`;
        const automationModule = await import(moduleUrl);
        if (typeof automationModule.handler !== 'function') {
            throw new Error('Downloaded project does not export lambda.handler');
        }
        const result = await automationModule.handler(event);
        return await handleResult(result);
    } finally {
        clearAutomationSecrets();
        await rm(invocationRoot, { recursive: true, force: true });
    }
}

export async function storeReport(report) {
    const body = report.reportPath
        ? await readFile(report.reportPath)
        : Buffer.from(report.csv, 'utf8');
    const now = new Date();
    const datePath = now.toISOString().slice(0, 10).replaceAll('-', '/');
    const bucket = required('REPORT_BUCKET');
    const prefix = required('REPORT_PREFIX').replace(/^\/+|\/+$/g, '');
    const filename = basename(report.filename);
    const key = `${prefix}/${datePath}/${now.toISOString().replaceAll(':', '-')}-${filename}`;

    await s3.send(new PutObjectCommand({
        Bucket: bucket,
        Key: key,
        Body: body,
        ContentType: 'text/csv',
        ServerSideEncryption: 'AES256',
    }));
    const downloadUrl = await getSignedUrl(
        s3,
        new GetObjectCommand({ Bucket: bucket, Key: key }),
        { expiresIn: Number(process.env.REPORT_URL_EXPIRATION_SECONDS || 3600) }
    );
    return {
        bucket,
        key,
        attachment: {
            filename,
            contentType: 'text/csv',
            size: body.length,
            downloadUrl,
        },
    };
}

function validateReport(report) {
    if (!report.title) {
        throw new Error('Report title is required');
    }
    if (!report.metrics || typeof report.metrics !== 'object' || Array.isArray(report.metrics)) {
        throw new Error('Report metrics must be an object');
    }
    if (Object.keys(report.metrics).length === 0) {
        throw new Error('Report metrics must not be empty');
    }
}

export async function publishWarningReport({
    eventName,
    report,
    storedReport,
    durationMs,
    context,
}) {
    validateReport(report);
    const environment = process.env.ENVIRONMENT_TYPE || 'unknown';
    const message = {
        schemaVersion: '1.0',
        eventId: context.awsRequestId || randomUUID(),
        eventType: 'report',
        producer: required('REPORT_PRODUCER'),
        eventName,
        occurredAt: new Date().toISOString(),
        severity: 'info',
        environment,
        title: report.title,
        data: {
            metrics: report.metrics,
            details: report.details,
            durationMs,
        },
        links: report.links,
        attachment: storedReport.attachment,
    };
    await sns.send(new PublishCommand({
        TopicArn: required('WARNING_SNS_TOPIC_ARN'),
        Subject: `[${environment}] ${report.title}`.slice(0, 100),
        Message: JSON.stringify(message),
    }));
    return {
        bucket: storedReport.bucket,
        key: storedReport.key,
        metrics: report.metrics,
    };
}
