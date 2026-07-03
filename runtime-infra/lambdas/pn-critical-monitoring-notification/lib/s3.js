const {
    S3Client,
    PutObjectCommand,
    ListObjectsV2Command,
    GetObjectCommand,
    DeleteObjectsCommand,
} = require("@aws-sdk/client-s3");

let getSignedUrl;
let AwsSdkV2;

try {
    ({ getSignedUrl } = require("@aws-sdk/s3-request-presigner"));
} catch (error) {
    console.warn("@aws-sdk/s3-request-presigner not available, trying aws-sdk v2 fallback.");
}

try {
    AwsSdkV2 = require("aws-sdk");
} catch (error) {
    console.warn("aws-sdk v2 not available for presigned URL fallback.");
}

const s3Client = new S3Client();

async function uploadFileToS3(bucket, key, content) {
    console.log(`Uploading object to ${key} in bucket ${bucket}`);
    const input = { // PutObjectRequest
        Bucket: bucket,
        Key: key, // required
        Body: content,
        ContentType: "application/json; charset=utf-8"
    };
    const command = new PutObjectCommand(input);
    const response = await s3Client.send(command);
    return response;
}

async function listObjectsByPrefix(bucket, prefix) {
    const objects = [];
    let continuationToken;

    do {
        const response = await s3Client.send(new ListObjectsV2Command({
            Bucket: bucket,
            Prefix: prefix,
            ContinuationToken: continuationToken,
        }));

        if (response.Contents) {
            objects.push(...response.Contents);
        }

        continuationToken = response.IsTruncated ? response.NextContinuationToken : undefined;
    } while (continuationToken);

    return objects;
}

async function downloadFileFromS3(bucket, key) {
    const response = await s3Client.send(new GetObjectCommand({
        Bucket: bucket,
        Key: key,
    }));

    if (!response.Body) {
        return "";
    }

    return response.Body.transformToString("utf-8");
}

async function deleteObjectsFromS3(bucket, keys) {
    if (!keys || keys.length === 0) {
        return;
    }

    const chunkSize = 1000;
    for (let i = 0; i < keys.length; i += chunkSize) {
        const chunk = keys.slice(i, i + chunkSize);
        await s3Client.send(new DeleteObjectsCommand({
            Bucket: bucket,
            Delete: {
                Objects: chunk.map((key) => ({ Key: key })),
                Quiet: true,
            },
        }));
    }
}

async function generatePresignedUrl(bucket, key, expiresInSeconds = 172800) {
    if (getSignedUrl) {
        return getSignedUrl(
            s3Client,
            new GetObjectCommand({ Bucket: bucket, Key: key }),
            { expiresIn: expiresInSeconds }
        );
    }

    if (AwsSdkV2) {
        const s3 = new AwsSdkV2.S3();
        return s3.getSignedUrlPromise("getObject", {
            Bucket: bucket,
            Key: key,
            Expires: expiresInSeconds,
        });
    }

    throw new Error("No presigned URL provider available. Install @aws-sdk/s3-request-presigner or provide aws-sdk v2.");
}

module.exports = {
    uploadFileToS3,
    listObjectsByPrefix,
    downloadFileFromS3,
    deleteObjectsFromS3,
    generatePresignedUrl,
};
