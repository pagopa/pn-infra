const AWS = require('aws-sdk')

exports.handler = async (event) => { 
    console.log( JSON.stringify(event, null, 2) );

    for( const record of event.Records ) {
        
        const msgBodyStr = record.body;
        const msg = JSON.parse( msgBodyStr );

        for ( const msgRec of msg.Records ) {
        
            const bucketName = msgRec.s3.bucket.name;
            const fileKey = msgRec.s3.object.key;
            
            console.log("bucketName=", bucketName, "fileKey=", fileKey)
            
            var s3 = new AWS.S3();
            var params = {Bucket: bucketName, Key: fileKey}
            var data = await readOne( s3, params )  
            console.log( data )
        }
    }
}


function readOne(s3, params) {
    return new Promise( (acc, rec) => {
        s3.getObject(params, function(err, data) {
            if (err) { rec(err) } else { acc(data) }
        });  
    })
}