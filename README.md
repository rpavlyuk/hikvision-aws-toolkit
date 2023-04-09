# Hikvision AWS Toolkit
A set of tools to manage captured files stored by Hikvision devices on FTP file shares: arrange them, upload them to AWS, rotate old files, etc. With this toolset you can enabled

## Background
I own Hikvision video surveillance system (a dozen of IP cameras from different generations and the NVR) and I was looking on how to store in the cloud the screenshot images which are captured when the security event is triggered. For example, you can set up a *Line Crossing Detection* event detection either on camera or the NVR, and once it happens (means something/-body is crossing that virtual line) device is taking a couple screenshots which are then stored ether on local storage (e.g., SD Card or HDD) or remote (e.g., FTP, SMB or similar). Problem is that when you have an intrusion into your home or office, intruder can also steal or destroy the reconding device, either NVR and/or your home server, making the whole idea of recording pointless. Thus, I came to an idea that I have to store captured surveillance events data somewhere outside my home and office.
Cloud is ideal for that purpose, but here come the problems:
* Placing FTP or SMB outside the firewall in the Internet is (a) very insecure and (b) very unrealiable. Will not explain much more here because it is obvious enough.
* Very latest Hikvision cameras support recording to OneDrive, but those older and simple ones -- don't. They aren't smart enough.
* In addition, Hikvision cameras dumps all event data into one folder so I have to sort and rotate them somehow.

How I overcame those challenges and limitation? Let me show you and hope will help you solving your challenge with storing security surveillance events in the cloud as well.

## Solution
High-level concept of HK AWS Toolkit which I created, goes below:
![HK AWS Toolkit concept](https://github.com/rpavlyuk/hikvision-aws-toolkit/blob/main/doc/hkawstoolkit_schema.png?raw=true)

The concept is the following: IP cameras send media information (typically, screenshots of the events) to FTP server, on which the proper folder is a mounted AWS S3 bucket using s3fs. Thus, the FTP server acts as an intemdiate relay: once the file is dropped via FTP -- it automatically lands in S3 backup. They the set of tools periodically sort, rotate and archive the files to Glacier, either automatically or manually.

**Import note:** This solution doesn't store/do video streaming to the cloud, just the screenshots captured during the triggeredevents. Storing streaming video is quite heavy task as of point of resources and, of course, money. Per my expereince, storing event screenshots in the cloud is enough to have a major breakthrough during the (potential) forensics investigation.

## Setup and Installation
### Preconditions
In order to make your Hikvision (and probably other system like DAHUA) as least partially Cloud-enabled, you need:
* Surveillance cameras itself. Actually, for our use case NVR is not even needed since in our case cameras will store captured images to FTP directly.
* AWS Account. My monthly cost to run this tool varies from 10 to 40 USD depending how much data is being pushed and is historically stored.
* Home / office server. Can be as simple as RaspberryPi-based box running any recent version of Linux.

The instruction below executed step by step shall guide shall make you run the solution.

### Setup AWS Bucket
* Goto https://s3.console.aws.amazon.com/s3/buckets and create a new bucket that you will use to store the data. You can also do it via API, it doesn't matter. Let's assume you named it *my-video-surveillance*.
* Few hints when creating the bucket:
  * Choose region closest to you
  * Make sure objects in it are not public
  * Versioning is not needed (unless you really-really want to and you know wny)
* Go to IAM page (https://us-east-1.console.aws.amazon.com/iamv2/home?region=us-east-1#/users) and create user that will access the bucket. Let's say, we will give it a name *home-cctv*. Note ACCESSKEY and SECRET as we will need them later and the secret appears only one time when you actaully create the user.
**NOTE:** Don't even think about using your root AWS account to access the bucket via tool. It is against all rules and patterns, and it is very unsecure!
* Now, go to *Policies* (https://us-east-1.console.aws.amazon.com/iamv2/home?region=us-east-1#/policies) and create new policy named *AllowS3AccessCCTVMonitoring*.
  * Choose 'JSON' format instead of visual editor and enter the following policy rules:
```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "s3:GetBucketLocation",
            "Resource": "arn:aws:s3:::*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:GetObjectTagging",
                "s3:PutObjectTagging",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::my-video-surveillance/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::my-video-surveillance"
            ]
        },
        {
            "Effect": "Allow",
            "Action": "s3:ListAllMyBuckets",
            "Resource": "arn:aws:s3:::*"
        }
    ]
}
```
  * This policy allows to read/write files (actually, objects) in the *my-video-surveillance* bucket, as well as list all available buckets in the account.
* Go back to users (https://us-east-1.console.aws.amazon.com/iamv2/home#/users) and assign newly created to policy to the user we've created above:
  * Select our *home-cctv* user (click on its name)
  * Go to section *Permission Policies*, select *Add Permissions* in the dropdown in top right corner of the panel.
  * New window will appear. Select *Attach Policies Directly* in the section *Permission Options*
  * *Permission policies* section will appear at the bottom. Find policy *AllowS3AccessCCTVMonitoring* that you've created, check it and press *Next*
  * Review if everything is correct and press *Add Permission*
* Now you're done with setting up the AWS part.


To be continued...
