const { CloudWatchClient, DescribeAlarmsCommand, PutMetricDataCommand } = require("@aws-sdk/client-cloudwatch");

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