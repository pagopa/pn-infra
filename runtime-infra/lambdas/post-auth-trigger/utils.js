import md5 from 'crypto-js';
import { PutObjectCommand, HeadObjectCommand } from "@aws-sdk/client-s3";

export const putObjectToS3 = async (s3Client, bucket, key, data, md5Hash) => {
    const params = {
        Bucket: bucket,
        Key: key,
        Body: data,
        ContentMD5: md5Hash
    };
    try {
        await s3Client.send(new PutObjectCommand(params));
        console.log("Successfully written to S3");
    } catch (err) {
        console.error("Error occurred in put object: ", err);
    }
};

export const checkIfUserExists = async (s3Client, bucket, key) => {
    const params = { Bucket: bucket, Key: key };
    try {
        await s3Client.send(new HeadObjectCommand(params));
        return true;
    } catch (err) {
        if (err.name === 'NotFound') return false;
        return true; // Per sicurezza su 403 o errori ignoti non sovrascriviamo
    }
};

export const getMD5HashFromFile = async (file) => {
    const hash = md5.MD5(file);
    return hash.toString(md5.enc.Base64);
};
