# Hikvision AWS Toolkit
A set of tools to manage captured files stored by Hikvision devices on FTP file shares: arrange them, upload them to AWS, rotate old files, etc. This toolset is all you need to store the captured event images on AWS Cloud (S3) and successfully manage them.

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
* Home / office server. Can be as simple as RaspberryPi-based box running any recent version of Linux. And of course, it must be behind the firewall and must be in the same local network as your cameras.

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

### Setup Linux server
#### Part 1: FTP Server
I'm using Fedora Linux so there might be commands specific to RedHat-based distros. However, I will not be using any RedHat-specific tools so running the setting up other distro like Ubuntu or Mint shall not be much different (if different at all).
* Setup FTP server. I'm using vsftpd (https://security.appspot.com/vsftpd.html) because it is easy in setup and is quite secure (although FTP protocol is insecure by itself!)
```
# On Redhat systems
sudo dnf install -y vsftpd

# On Debian systems
sudo apt-get install vsftpd
```
* Enable PAM authentication for FTP server. Edit file */etc/vsftpd/vsftpd.conf* and ensure it has the following lines (typically at the bottom):
```
pam_service_name=vsftpd
userlist_enable=YES
```
* Create directory where you will store the captured images from cameras and mount the S3 bucket:
```
# change /var/lib/cctv part to anyone you'd like
sudo mkdir -p /var/lib/cctv/storage
```
* Create *cctv* user that will be used by cameras to login via FTP:
```
sudo adduser -d /var/lib/cctv -s /bin/false cctv
```
* And change its password:
```
sudo passwd cctv
```
* Make *cctv* owner if its home directory:
```
sudo chown -R cctv /var/lib/cctv
```
* (Re)start FTP server:
```
systemctl restart vsftpd
```
* Test login from another server or client to the newly started FTP server:
```
# EXAMPLE: Assuming 192.168.1.2 is the ip of the box where you just installed VSFTPD
[rpavlyuk@gemini ~]$ ftp 192.168.1.2
Connected to 192.168.1.2 (192.168.1.2).
220 (vsFTPd 3.0.5)
Name (192.168.1.2:rpavlyuk): cctv
331 Please specify the password.
Password:
```
#### Part 2: S3FS mount
S3FS (https://github.com/s3fs-fuse/s3fs-fuse) is the software which allows you to mount S3 bucket into Linux folder and use like a filesystem.
* Go to https://github.com/s3fs-fuse/s3fs-fuse and follow the installation procedure up to the point when it tells you to modify */etc/fstab* file. You will need ACCESSKEY and SECRET for the AWS user which we've created in the section above. If didn't save the SECRET... well.. you will need to get a new access key for the user again.
* New, let's add the corresponding entry to */etc/fstab* file. This is the file which allows you to mount the filesystem on boot or login. Add this line at the end of the file:
```
# Remote S3 CCTV storage
s3fs#my-video-surveillance /var/lib/cctv/storage fuse nonempty,_netdev,allow_other,use_cache=/var/tmp,ensure_diskfree=30720,max_stat_cache_size=250000,passwd_file=/etc/passwd-s3fs,url=https://s3.eu-central-1.amazonaws.com,umask=0000 0 0
```
**NOTE**: Replace 'eu-central-1' with the name of the region where your bucket is stored. You will find it in AWS S3 Console, where all buckets are listed.
* Once the file is saved, it is time to test:
  * Mount the folder:
```
mount /var/lib/cctv/storage
```
  * Put dummy file in the folder:
```
touch /var/lib/cctv/storage/test.file
```
  * Go to https://s3.console.aws.amazon.com/s3/buckets, open bucket *my-video-surveillance* and if file *test.file* appeared -- congrats, you have s3fs confgured!
  
