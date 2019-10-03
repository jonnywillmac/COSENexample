# Example script to generate Video Metadata To be stored alongside the object
# Bare bones example and not suggested for use in production there is no error handling
# in place
#
# Jonathan McCormick
# jmccormick@uk.ibm.com

import ibm_boto3
import json
import subprocess
from ibm_botocore.client import Config


# Function to return a pre-signed URL that will allow the read of a object
# for a limited time and without credentials.  In this case 5 minutes.
def getURL(client,key, bucket):
    response = client.generate_presigned_url(
            'get_object',
            Params={
            'Bucket': bucket,
            'Key': key
            },
            ExpiresIn=300
            
    )
    return response

# Function to upload passed string as an object
def putObject(client, key, bucket, data):
        response = client.put_object(
                Body=data,
                Bucket=bucket,
                Key=key
        )
        return response

def main(params):

        # First Check that this is a new object - we do not want this function to
        # run for updates or deletes
        if params['notification']['event_type'] != 'Object:Write':
                return {'Result': 'Nothing added'}
        else:
                # Take parameters passed to the function to populate our variables
                source_service_endpoint = 'https://' + params['endpoint']
                bucketName= params['bucket']
                
                #HMAC CREDS
                access_key_id = params['__bx_creds']['cloud-object-storage']['cos_hmac_keys']['access_key_id']
                secret_access_key = params['__bx_creds']['cloud-object-storage']['cos_hmac_keys']['secret_access_key']

                # Object name we're going to read and create the name for the metadata object
                # we have a prefix in case a simple search for metadata in the bucket is needed
                # suffix to ensure we don't have the function firing twice when the metadata is written
                objectName= params['key']
                metadataName = 'metadata/' + objectName + '.meta'

                # Use the creds to create our client to write to COS
                cos = ibm_boto3.client('s3',
                        aws_access_key_id=access_key_id,
                        aws_secret_access_key=secret_access_key,
                        endpoint_url=source_service_endpoint)

                # Call function to provide a presigned URL for ffprobe to read
                url = getURL(cos, objectName, bucketName)

                
                command = ['ffprobe', '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', url]
                p = subprocess.Popen(command, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                output = p.stdout.read()

                parsed = json.loads(output)
                putObject(cos,metadataName,bucketName,output)

                return parsed