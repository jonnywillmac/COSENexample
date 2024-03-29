# Working with IBM Cloud Object Storage and Event notifications
#CloudObjectStorage #CloudFunctions

One of the features of Cloud Object Storage I find clients are keen to use, but can find hard to implement is Event Notifications..  This is functionality that can take a number of forms, but, in all cases the basic idea is; that an object comes into the object store (or is updated, deleted) and when this happens the ‘event’ is pushed onto a message queue ready for some type of consumer to act on.  In cloud environments the most common way to ‘consume’ the event is via a Cloud Function. 

IBM Cloud Object Storage has had this functionality for some time now, albeit with an “experimental” tag.  As such I’ve been using the service for a number of months now and, with the imminent GA of service, thought I’d share a simple example of how one might go about implementing a cloud function integrated with COS event notifications. 

The example I’ve chosen is one which I put together for one of our media customers.  It’s chosen because whilst relatively simple, it does require the use of some more advanced features (like a specific container build) so I hope will keep the interest of both new users and those who are more experienced.   I have purposefully gone into detail on each step to ensure this is accessible to all.

## Our Requirement
The requirement is thus - In the event of a video file being uploaded to the object store and job is triggered that will interrogate the object and return details of the container type, codec, resolution and duration of the video.  When these details are established they will be stored on the object store alongside the object as a metadata object. 

 ::INSERT SOME KIND OF EXAMPLE HERE?::

## The Challenge
Quite a simple requirement, but not something that is trivial where data resides on an object store and we’re looking to leverage a cloud function which is transient by nature.  One of the main challenges here is that generally when interrogating an object you would pull to the filesystem first.  This has little impact when we’re talking about smaller file types, however, has larger implications when considering server-less functions.  Local disk space can be limited and does vary between providers.   Whilst IBM Cloud Functions has a generous limit of ::xxGB:: it still cannot cope with the larger file sizes media files generally command. 

Ideally what’s needed here is a tool to interrogate the file which will provide the ability to stream the data from the object store rather than it requiring the data is stored on the local filesystem.  Luckily, the most popular open source tool available is already able to do this.  ffmpeg (or specifically in this case ffprobe) is designed to take media from multiple sources.  One of these sources is a http stream.  Conveniently when performing a GET (object storage operation to retrieve the data) on an object it in essence provides a http stream.  So if we provide the ffprobe with a URL to access we can avoid having to store the media on a local filesystem. 

## The Solution
So based on the above, the workflow for our event and function will look like this… 

![](unknown.png)

Simple right?  In theory yes, so let’s discuss the components we’re going to need to build this solution. 

## Pre-requisites
OK, so there’s a few things that are needed if we’re going to work through this example. 

1. IBM Cloud Account - sign up at  [https://cloud.ibm.com](https://cloud.ibm.com/) 
2. IBM Cloud CLI - in an effort to ensure clarity and promote the message that “command line is fun” we’ll use the Cloud CLI to create all resources.  Get it here  [https://github.com/IBM-Cloud/ibm-cloud-cli-release/releases/](https://github.com/IBM-Cloud/ibm-cloud-cli-release/releases/) .  You’ll need to make sure you’re logged in and can query cloud resources.
3. IBM Cloud CLI COS Plugin - [IBM Cloud Docs](https://cloud.ibm.com/docs/cloud-object-storage?topic=cloud-object-storage-ic-use-the-ibm-cli)
4. Access to docker and a registry.  This is optional as you can skip the container build step and simply use the container I use in my example.  But where’s the fun in that?. 
5. A source code editor (or simply notepad at a push). 

## Create a bucket
With our pre-requisites in place we’re now ready to start creating the workflow outlined above.  Firstly, bucket creation.  This will be the location our videos are uploaded to and also where the metadata object will also be placed.  The steps to do this using the CLI are as follows.

**Create a resource Group** - it helps when working on projects to group all common resources for that project into a resource group.   Once created resource groups cannot be deleted so you can always rename an existing group if you’d prefer.

`ibmcloud resource group-create COSexample`

Then to ensure all our CLI operations use this resource group.

`ibmcloud target -g COSexample`

At this stage, the output from the `ibmcloud target` command should look something like this

```
Targeted resource group COSexample


                      
API endpoint:      https://cloud.ibm.com  
Region:            us-south   
User:              jmccormick@uk.ibm.com   
Account:           Jonathan McCormick’s Account (1a11a11a11a11aa11111aa1111a11111) <-> 1234567   
Resource group:    COSexample   
CF API endpoint:      
Org:                
Space: 
```

**Create IBM Cloud Object Storage Service** - provision a COS service in order to be able to create the bucket.  Services are created with the `resource service-instance-create` command.  There’s a few parameters needed here

`NAME` - simply the name of your instance - I’m going to use COS
`SERVICE NAME` - the name of the service type you’re creating. In this case cloud-object-storage.
`SERVICE PLAN NAME` - one option here for COS - standard
`LOCATION` - COS is a `global` service.

The command therefore to create the instance - this will create the service in your target resource group (in this case COSexample)

`ibmcloud resource service-instance-create COS cloud-object-storage standard global`

Confirmation of success will include the ID of your service instance.   It will look something like this

``` 
*ID:*                    crn:v1:bluemix:public:cloud-object-storage:global:a/7d13c77c51e93be75993ee1148f54338:xxxxxxxx-xxxx-xxxx-xxxx-6796e5b2e003::   
```

This is needed to access the service from the COS plugin.   Take a copy and, assuming you have installed the COS plugin run the following command.

`ibmcloud cos config crn`

When prompted, paste in the ID / CRN you have copied.   If successful you should be able to run the following command and receive the following response.

```
ibmcloud cos list-buckets
*OK*
No buckets found in your account.
```

With this now working we can create the bucket just use the following command (but change the bucket name!).  If steps so far have matched it will create a standard bucket in the us-south region.

```
ibmcloud cos create-bucket --bucket placetouploadvideo
*OK*
Details about bucket *placetouploadvideo*:
Region: *us-south*
Class: *Standard*
```

## Object PUT
There are lots of ways we can achieve this.  For example if you’ve followed the create bucket steps above

`ibmcloud cos upload --bucket placetouploadvideo --key newobjectname --file /path/to/file`

This will upload an object to COS.

For a production use case we want to streamline the upload as much as possible.  As we’re talking large files we need multipart parallelised uploads.  Many S3 Compatible clients can achieve this.  As this isn’t the main purpose of this blog I’m not going to implement anything specific for this - especially as we have enterprise class functionality in the form of Aspera built right into the IBM Cloud Console.  With the quick installation of the Aspera client libraries we can use industry standard methods of getting the media file directly to Cloud Object Storage. 

## Configuring your account to use Cloud Functions
As a recap you’ll remember we’ve setup within our account a Resource Group (in my case called COSexample).  This ensures that any cloud resources we create for this project are grouped together.  In addition to this we also need to provide a namespace  for our Cloud Functions to run in.  This is as simple as creating and targeting the name space.

`ibmcloud fn namespace create COSfnexample`

`ibmcloud fn property set --namepsace COSfnexample`

With this completed we are able to now configure the Event service to monitor our bucket.  For this we need the notifications manager role assigned to our namespace.  You must be account admin in order to do this.

```
ibmcloud iam authorization-policy-create functions \
cloud-object-storage 'Notifications Manager' \
--source-service-instance-name COSfnexample \
--target-service-instance-name COS
```

## Creating COS service credentials
When we create our function to query the object store we don’t want to have to embed security credentials into the code.  Generally we can use IAM to ensure that the function has access to the COS bucket, however, there are certain object operations that require service credentials and pre-signed URL operations are some of them.  To make sure we have credentials shared and useable in the code we need to bind our service creds to the action.  But first lets generate service credentials for our COS service and ensure HMAC credentials are included.

```
ibmcloud resource service-key-create COSserviceKey Manager —instance-name COS  \
-p ‘{“HMAC”: true}’
```

## Creating a trigger
With the  configuration so far , you can now monitor notifications from the COS instance.  In order to react to them we need a trigger.  The trigger is related to a specific bucket and allows us to “trigger” actions depending on the message content.  As we’re storing data and metadata in the same location we also want to ensure that the trigger is only for video files.  We’ll add the .mp4 suffix to do this as this is the container formation being used in this example.

The command to achieve this is as follows

```
ibmcloud fn trigger create cosTrigger --feed /whisk.system/cos/changes \
--param bucket placetouploadvideo \
--param suffix .mp4
```

With this done it’s time to look at the code which will run in our action.

## Creating the Function
The code to run here is relatively simple and there a number of languages that IBM cloud functions supports right out of the box.  In this case, however, there’s an additional challenge.   As we need to use a third party application to interrogate the video file (ffprobe) we need to ensure the runtime environment includes this.  The default python runtimes do not have this included so once we have our working code we will need to build a container that has what we need.

Rather than go into detail on the code itself in this case I’m going to simply provide a GitHub link.  This includes the commented python function we’ll use and also the Dockerfile that we’re using in the next step.

The repo is here [GitHub - jonnywillmac/COSENexample](https://github.com/jonnywillmac/COSENexample)

[generateVideoMetadata.py](https://github.com/jonnywillmac/COSENexample/blob/master/generateVideoMetadata.py) - is the file we’ll use when we create our action.

## Creating a container with ffprobe support
As previously discussed, if the standard runtimes we have available don’t quite meet our requirements, we can create our own container that does.   If you’re not interested in this step, or simply don’t have docker available on your system and an account, then you can move straight to creating the action. 

### Verify docker is installed and configured
Before continuing ensure that docker is installed and functioning.  A simple way to test this is with the hello-world container.  Simply run the following and ensure it completes correctly.

You should see the following if so we’re ready to go!

```
$ docker run hello-world
Unable to find image ‘hello-world:latest’ locally
latest: Pulling from library/hello-world
1b930d010525: Pull complete 
Digest: sha256:b8ba256769a0ac28dd126d584e0a2011cd2877f3f76e093a7ae560f2a5301c00
Status: Downloaded newer image for hello-world:latest

Hello from Docker!
This message shows that your installation appears to be working correctly.
........
```

### Build our new container
IBM make it simple to build bespoke container.  There are base containers available specifically for this purpose.  In this case as I’m planning use python3 as will base my container on this image.

[ibmfunctions/action-python-v3.7](https://hub.docker.com/r/ibmfunctions/action-python-v3.7)

This container is built and ready to work with our action and contains the python 3 runtime environment.  All we need to do is add into this the ffprobe binary (part of the ffmpeg suite) and ensure that the cos python SDK’s are installed.  We do this using a Dockerfile which defines the steps to build our own container (based on the IBM one).

The Dockerfile looks like this

```
# Start with this container as the base
FROM ibmfunctions/action-python-v3.7

# add package build dependencies
RUN apt update
RUN apt install -y \
        ffmpeg

# add python packages
RUN pip3 install --upgrade pip
RUN pip3 install \
    ibm_cos_sdk
```

As you can see the steps are simple:

* Take the IBM base image
* Ensure the packages within are up to date
* Install ffmpeg (and any dependencies)
* Upgrade and run pip to install the IBM COS SDK

All we need to do is save this in a file called Dockerfile and cd into the folder containing it.  If you’re using the repo then the Dockerfile is part of this.  We also need to name the image in my case it’s called jonnywillmac/python_ibm_runtime this first part should match your docker user name (if using a Docker registry).  This is important so that when we push the image it’s uploaded to your registry ready for public use.  The command to build our container is then

`docker build -t <dockername>/<image name> .`

So for my example

`docker build -t jonnywillmac/python_ibm_runtime .`

You will see the correct images pulled and then the output as the steps we defined in the Dockerfile are carried out.  There will be a few warnings but should be no errors.

```
docker build -t jonnywillmac/python_ibm_runtime .
Sending build context to Docker daemon    108kB
Step 1/5 : FROM ibmfunctions/action-python-v3.7
 —> bd733161ee54
Step 2/5 : RUN apt update
 —> Running in 983f14d614c2
...
```

Finally we need to push the image to the docker registry so it can be used in our action

`docker push jonnywillmac/python_ibm_runtime`

```
$ docker push jonnywillmac/python_ibm_runtime
The push refers to repository [docker.io/jonnywillmac/python_ibm_runtime]
8053c0a99dae: Pushed 
023423d42f78: Pushed 
f090a220f4bf: Pushed 
381f99918f39: Pushed 
aec0068407cf: Mounted from ibmfunctions/action-python-v3.7 
8fcf91f2ffb1: Mounted from ibmfunctions/action-python-v3.7 
...
```

With this complete we can now look to create our action.


## Creating the Action
Now we have the function code and container within which it should be ran, it’s straightforward to create the action.  Format of the cli command is as follows

`ibmcloud fn action create cosProbe /<path to your folder>/COSEVexample/generateVideoMetadata.py --docker <dockername>/<image name>`

This uses default  for all parameters and run in the resource group and namespace set in previous step.  So for my example, to create the action the command is

`ibmcloud fn action update cosProbe ~/Code/Python/COSEVexample/generateVideoMetadata.py --docker jonnywillmac/python_ibm_runtime`

Confirm everything is configured as expected with

`ibmcloud fn list`

```
Entities in namespace: **default**
packages
actions
/634a6745-2596-497e-8f99-b1b23e4eec5b/cosProbe                         private blackbox
triggers
/634a6745-2596-497e-8f99-b1b23e4eec5b/cosTrigger                       private
```

## Binding credentials to our action
Earlier in this tutorial we created service credentials for our COS service.  This allows us to gain access to the bucket from within our function.  However, we don’t want to directly embed these credentials into the function as this would be a security risk.  Invariably when I’ve experimented with code and embedded credentials into it they always seem to end up in a GitHub repo no matter how many times I’ve made this mistake!  I’ve found the best way to avoid this is to avoid any kind of credentials being explicit in my code.

This means we need our functions service to retrieve the credentials for us.  For this to happen we need to “bind” the creds to our action.  Use the following taking not of your instance name and service key name.

```
ibmcloud fn service bind cloud-object-storage cosProbe \
--instance COS --keyname COSserviceKey
```

## Creating a Rule
The final step in the process is to link the trigger and the action.  Basically something which say when this happens - do this.  This is called a rule and is a simple to create as it sounds.

`ibmcloud fn rule create <Rule Name> <Trigger Name> <Action Name>`

So for our example 

`ibmcloud fn rule create cosRule cosTrigger cosProbe`

`ok: created rule **cosRule**`

With this in place our example workflow should be ready to test.  To make sure run `ibmcloud fn list` output should be similar to mine.

```
Entities in namespace: default
packages
actions
/634a6745-2596-497e-8f99-b1b23e4eec5b/cosProbe                         private blackbox
triggers
/634a6745-2596-497e-8f99-b1b23e4eec5b/cosTrigger                       private
rules
/634a6745-2596-497e-8f99-b1b23e4eec5b/cosRule                          private              active
```

## Testing the solution
To verify this is working as intended you’ll need a video file with an mp4 extension. Just a google of “open source video sample” gave me a couple of websites where it’s easy to download some example if you don’t have anything local.

### Upload video to COS bucket
We’ve already configured the cli so that it can access the COS bucket.  So to add the video file run the following command:

```
ibmcloud cos upload --bucket placetouploadvideo --key video.mp4 --file video.mp4
```

Make sure to update this to reflect the name of your bucket.  The key is the object name and the file is the path to your sample video file you’re using.  This should be the result

```
$ ibmcloud cos upload —bucket placetouploadvideo —key video.mp4 —file video.mp4
	**OK**
Successfully uploaded object ‘**video.mp4**’ to bucket ‘**placetouploadvideo**’.
```

### List Activations
With our object uploaded we need to verify the activation has been triggered and the rule and action ran.  The place to check this is within the list of activations - as with all the steps take here this can be done via CLI or UI.  The CLI command to verify what activations have taken place is.

`ibmcloud fn activation list`

You should see an output similar to this

```
**Datetime            Activation ID                    Kind      Start Duration   Status            Entity**
2019-10-04 09:59:53 3484a2d3fe0847dd84a2d3fe0867dd49 blackbox  cold  2.068s     success           634a6745-2…e4eec5b/cosProbe:0.0.16
2019-10-04 09:59:52 94fdf406e4d14003bdf406e4d10003df unknown   warm  0s         success           634a6745-2…e4eec5b/cosTrigger:0.0.1
```

You can see from the above that the first entry details the trigger being activated.  The second is the cosProbe function then being ran for the event.  You can see more detail on this with the commands

```
ibmcloud fn activation result  <Activation ID>
```

Assuming successful this should output the metadata we’ve written to the Object Store.

### List Objects
Finally to confirm we have what we need we can list the contents of the object store again you can browse through the UI at cloud.ibm.com to do this.  Do list the objects in our bucket you can use a command similar to this

```
$ ibmcloud cos list-objects --bucket placetouploadvideo
**OK**
Found 2 objects in bucket ‘**placetouploadvideo**’:

**Name**                      **Last Modified**              **Object Size**   
**metadata/video.mp4.meta**   Oct 04, 2019 at 08:59:55   2.38 KiB   
**video.mp4**                 Oct 04, 2019 at 08:59:48   26.59 MiB 
```

## Conclusion
So hopefully you’ve been able to work through this example and get a feel for how easy it is to make something useful with Event Notifications and Cloud Functions.

Much more detail is available at https://cloud.ibm.com in our documentation.   I recommend you check out the following links.

[IBM Cloud Object Storage](https://cloud.ibm.com/docs/cloud-object-storage)
[IBM Cloud Functions](https://cloud.ibm.com/docs/openwhisk)
