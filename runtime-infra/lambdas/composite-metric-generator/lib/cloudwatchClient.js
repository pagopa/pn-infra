const { CloudWatchClient, DescribeAlarmsCommand, PutMetricDataCommand } = require("@aws-sdk/client-cloudwatch");
const { STSClient, AssumeRoleCommand } = require("@aws-sdk/client-sts");

const getCrossAccountCredentials = async (accountId) => {
    
    // a client can be shared by different commands.
    const client = new STSClient({ region: process.env.REGION });
    
    const crossAccountRoleArn = `arn:aws:iam::${accountId}:role/CloudWatch-CrossAccountSharingRole`
    const timestamp = (new Date()).getTime();
    const params = {
        RoleArn: crossAccountRoleArn,
        RoleSessionName: `cross-account-credentials-${timestamp}`
    };
    const command = new AssumeRoleCommand(params);
    // async/await.
    try {
        const data = await client.send(command);
      // process data.
      return data;
    } catch (error) {
      // error handling.
      console.log(error)
      return null;
    }
}
async function getActiveAlarms(alarmNames, region){
    // a client can be shared by different commands.
    const client = new CloudWatchClient({ region: region });

    const params = {
        AlarmNames: alarmNames,
        StateValue: 'ALARM'
    };
    const command = new DescribeAlarmsCommand(params); 

    // async/await.
    try {
        const data = await client.send(command);
        // process data.
        if(data.MetricAlarms){
            console.info('Metric alarms', data)
            return data.MetricAlarms
        } else {
            console.warn('No metric alarms', data)
            return []
        }
    } catch (error) {
        // error handling.
        console.error(err)
        return null;
    }
}

async function putMicroserviceMetric(metricName, value, region){
    // a client can be shared by different commands.
    const client = new CloudWatchClient({ region: region });

    const namespace = ''
    const input = {
        MetricData: [
            {
                MetricName: metricName,
                Value: value,
            },
        ],
        Namespace: 'PnStatus',
    };

    const command = new PutMetricDataCommand(input);
    
    try {
        await client.send(command);
        return true;
    } catch (error) {
        console.error('Unable to put metric', {
            error: error,
            metricName: metricName,
            value: value
        })
        return false;
    }
}

module.exports = {
    getActiveAlarms,
    putMicroserviceMetric
}