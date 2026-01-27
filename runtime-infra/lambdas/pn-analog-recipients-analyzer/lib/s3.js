const { S3Client, PutObjectCommand } = require("@aws-sdk/client-s3");

const s3Client = new S3Client();

async function uploadFileToS3(bucket, key, content) {
    console.log(`Uploading object to ${key} in bucket ${bucket}`);
    const input = { // PutObjectRequest
        Bucket: bucket,
        Key: key, // required
        Body: content,
        ContentType: "text/csv; charset=utf-8"
    };
    const command = new PutObjectCommand(input);
    const response = await s3Client.send(command);
    return response;
}

module.exports = {
  uploadFileToS3
};
