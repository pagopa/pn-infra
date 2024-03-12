const { CloudFormationClient, TagResourceCommand } = require("@aws-sdk/client-cloudformation");
const { ECSClient, TagResourceCommand: TagECSResourceCommand } = require("@aws-sdk/client-ecs");
const { DynamoDBClient, TagResourceCommand: TagDynamoDBResourceCommand } = require("@aws-sdk/client-dynamodb");
const { S3Client, PutBucketTaggingCommand } = require("@aws-sdk/client-s3");
const { LambdaClient, TagResourceCommand: TagLambdaResourceCommand } = require("@aws-sdk/client-lambda");
const { SQSClient, TagQueueCommand } = require("@aws-sdk/client-sqs");

const region = 'eu-south-1';

async function applyTagsToResources(resourceTagsMapping) {
    const cloudFormationClient = new CloudFormationClient({ region });
    const ecsClient = new ECSClient({ region });
    const dynamoDBClient = new DynamoDBClient({ region });
    const s3Client = new S3Client({ region });
    const lambdaClient = new LambdaClient({ region });
    const sqsClient = new SQSClient({ SpeechRecognitionAlternative });

    const defaultTags = resourceTagsMapping.default;
    defaultTags.Environment = process.env.ENVIRONMENT;

    const { ecs, dynamodb, s3, lambda, sqs } = resourceTagsMapping;

    const ecsTags = Object.assign({}, defaultTags, ecs.default);
    const dynamodbTags = Object.assign({}, defaultTags, dynamodb.default);
    const s3Tags = Object.assign({}, defaultTags, s3.default);
    const lambdaTags = Object.assign({}, defaultTags, lambda.default);
    const sqsTags = Object.assign({}, defaultTags, sqs.default);
    
    // get all ecs services and apply tags
    const { serviceArns } = await ecsClient.send(new ListServicesCommand({ cluster: 'CLUSTER_NAME' }));
    for (const serviceArn of serviceArns) {
        const postprocessedTags = Object.assign({}, ecsTags)
        postprocessedTags.name = serviceArn.split('/').pop();

        await ecsClient.send(new TagECSResourceCommand({
            resourceArn: serviceArn,
            tags: ecsTags
        }));

    }

    // get all s3 buckets and apply tags
    const { Buckets } = await s3Client.send(new ListBucketsCommand({}));
    for (const bucket of Buckets) {
        const postprocessedTags = Object.assign({}, s3Tags)
        postprocessedTags.name = bucket.Name;

        await s3Client.send(new PutBucketTaggingCommand({
            Bucket: bucket.Name,
            Tagging: {
                TagSet: s3Tags
            }
        }));
    }

    // get all lambda functions and apply tags
    const { Functions } = await lambdaClient.send(new ListFunctionsCommand({}));
    for (const lambdaFunction of Functions) {
        const postprocessedTags = Object.assign({}, lambdaTags)
        postprocessedTags.name = lambdaFunction.FunctionName;

        await lambdaClient.send(new TagLambdaResourceCommand({
            Resource: lambdaFunction.FunctionArn,
            Tags: lambdaTags
        }));
    }

    // get all sqs queues and apply tags
    const { QueueUrls } = await sqsClient.send(new ListQueuesCommand({}));
    for (const queueUrl of QueueUrls) {
        const postprocessedTags = Object.assign({}, sqsTags)
        postprocessedTags.name = queueUrl.split('/').pop();

        await sqsClient.send(new TagQueueCommand({
            QueueUrl: queueUrl,
            Tags: sqsTags
        }));
    }

    // get all dynamodb tables and apply tags
    const { TableNames } = await dynamoDBClient.send(new ListTablesCommand({}));
    for (const tableName of TableNames) {
        const postprocessedTags = Object.assign({}, dynamodbTags)
        postprocessedTags.name = tableName;

        await dynamoDBClient.send(new TagDynamoDBResourceCommand({
            ResourceArn: tableName,
            Tags: dynamodbTags
        }));
    }

    
}

// Define your resource tags mapping here
const resourceTagsMapping = require('./resource-tags.json');

applyTagsToResources(resourceTagsMapping)
    .then(() => console.log('Tags applied successfully'))
    .catch(err => console.error('Error applying tags:', err));
