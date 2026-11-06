const {
    S3Client,
    PutObjectCommand,
} = require("@aws-sdk/client-s3");

function integerSetting(name, fallback, min, max) {
    const value = process.env[name] === undefined ? String(fallback) : process.env[name];
    if (!/^\d+$/.test(value) || !Number.isSafeInteger(Number(value)) ||
        Number(value) < min || Number(value) > max) {
        throw new Error(`${name} must be an integer between ${min} and ${max}`);
    }
    return Number(value);
}

const maxRetries = integerSetting("S3_MAX_RETRIES", 3, 0, 3);
const uploadBudgetMs = integerSetting("S3_UPLOAD_BUDGET_SECONDS", 45, 1, 900) * 1000;
const timeoutMarginMs = 5000;
const s3Client = new S3Client({
    retryMode: "standard",
    maxAttempts: maxRetries + 1,
});

async function uploadFileToS3(bucket, key, content, remainingTimeMs) {
    if (!Number.isFinite(remainingTimeMs) || remainingTimeMs <= timeoutMarginMs) {
        throw new Error("Insufficient Lambda time remaining for S3 upload");
    }
    const budgetMs = Math.min(uploadBudgetMs, remainingTimeMs - timeoutMarginMs);
    const controller = new AbortController();
    const startedAt = Date.now();
    let timer;
    const deadline = new Promise((resolve, reject) => {
        timer = setTimeout(() => {
            const error = new Error(`S3 upload exceeded its ${budgetMs} ms budget`);
            error.name = "UploadDeadlineExceededError";
            reject(error);
            controller.abort();
        }, budgetMs);
    });
    const input = {
        Bucket: bucket,
        Key: key,
        Body: content,
        ContentType: "application/json; charset=utf-8"
    };
    try {
        // The deadline also bounds SDK backoff waits, not just HTTP requests.
        const response = await Promise.race([
            s3Client.send(new PutObjectCommand(input), { abortSignal: controller.signal }),
            deadline,
        ]);
        console.log("S3 upload completed", {
            durationMs: Date.now() - startedAt,
            attempts: response.$metadata.attempts,
            totalRetryDelay: response.$metadata.totalRetryDelay,
        });
        return response;
    } catch (error) {
        console.error("S3 upload failed", {
            name: error.name,
            httpStatusCode: error.$metadata?.httpStatusCode,
            attempts: error.$metadata?.attempts,
            totalRetryDelay: error.$metadata?.totalRetryDelay,
            durationMs: Date.now() - startedAt,
        });
        throw error;
    } finally {
        clearTimeout(timer);
    }
}

module.exports = {
    uploadFileToS3,
};
