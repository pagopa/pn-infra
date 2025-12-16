//create s3 client in order to upload files to s3
const { S3Client, PutObjectCommand } = require("@aws-sdk/client-s3");

const s3Client = new S3Client();

//function that upload file to bucket s3
async function uploadFileToS3(bucketName, key, body) {
    const input = { // PutObjectRequest
        Bucket: bucketName,
        Key: key, // required
        Body: body,
        ContentType: "text/csv; charset=utf-8"
    };
    const command = new PutObjectCommand(input);
    const response = await s3Client.send(command);
    return response;
}


module.exports = {
  uploadFileToS3
};
