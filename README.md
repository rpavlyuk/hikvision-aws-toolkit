# Hikvision AWS Toolkit
A set of tools to manage captured files as the result of the triggered event stored by Hikvision devices on FTP file shares: arrange them, upload them to AWS, rotate old files, etc. This toolset is all you need to store the captured event images on AWS Cloud (S3) and successfully manage them.

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
* Goto https://s3.console.aws.amazon.com/s3/buckets and create a new bucket that you will use to store the data. You can also do it via API, it doesn't matter. Let's assume you named it `my-video-surveillance`.
* Few hints when creating the bucket:
  * Choose region closest to you
  * Make sure objects in it are not public
  * Versioning is not needed (unless you really-really want to and you know wny)
* Go to IAM page (https://us-east-1.console.aws.amazon.com/iamv2/home?region=us-east-1#/users) and create user that will access the bucket. Let's say, we will give it a name `home-cctv`. Note ACCESSKEY and SECRET as we will need them later and the secret appears only one time when you actaully create the user.
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
* As part of the installation, 's3fs' may require you to create a special file with your access key and secret. You can do it by issuing the command (not forget to replace ACCESS_KEY_ID and SECRET_ACCESS_KEY with those real ones that we created in section '*Create AWS Bucket*')
```
echo ACCESS_KEY_ID:SECRET_ACCESS_KEY > /etc/passwd-s3fs
chmod 600 /etc/passwd-s3fs
```
* New, let's add the corresponding entry to */etc/fstab* file. This is the file which allows you to mount the filesystem on boot or login. Add this line at the end of the file:
```
# Remote S3 CCTV storage
s3fs#my-video-surveillance /var/lib/cctv/storage fuse nonempty,_netdev,allow_other,use_cache=/var/tmp,ensure_diskfree=30720,max_stat_cache_size=250000,passwd_file=/etc/passwd-s3fs,url=https://s3.eu-central-1.amazonaws.com,endpoint=eu-central-1,umask=0000 0 0
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
  
### Setup IP Cameras
* Log into your camera through WEB interface and setup FTP server connection:
![FTP Server configuration for Hikvision IP Camera](https://user-images.githubusercontent.com/3177468/230902583-e515bc44-8991-48a0-80a3-7b8401b2d524.png)

  * *Parent Directory* is a subdirectory in the FTP root. I suggest you set it as *storage*, as we did it in the section above.
  * *Child Directory* shall be equal to camera name. Camera name is being set as *Device Name* in *System Settings* section of camera configuration.

* For the events you want to capture, enable saving screenshot images to the FTP:
![Save event data to FTP](https://user-images.githubusercontent.com/3177468/230903793-98ff5421-3092-4a2b-a6e9-fdddbbc93cfa.png)

* Configure the capture parameters, especially how many photos to take when event is triggered and with which interval:
![Configure event capture](https://user-images.githubusercontent.com/3177468/230904461-24a80896-bab6-4f98-a6aa-3d2b4732ee01.png)

* You can also adjust capture schedule, for example, if you do not want to capture events during night, day or weekend.

**NOTE:** Settings interface may differ from model to model and from vendor to vendor.

### Setup HK AWS Toolkit
* Go back to your Linux server. Go to your home directory, checkout the source code from this repository and enter source directory:
```
cd && git clone https://github.com/rpavlyuk/hikvision-aws-toolkit.git && cd hikvision-aws-toolkit
```
* Install required system tools:
```
# RedHat systems 
sudo dnf install -y python3 make perl-interpreter

# Debian systems
sudo apt-get install python3 make perl
```
* Install *s3fs* support tools (replace variable values with the yours if needed):
```
sudo make s3fs-tool S3BUCKET=my-video-surveillance S3FSMOUNTFOLDER=/var/lib/cctv/storage
```
* This actions installs two recommended tools to use:
  * S3FS connection watchdog, which will try to restore s3fs mount point
  * S3FS cache cleaner which will prevent the cache from use if too much space
  Both tools are executed by CRON on regular basis on behalf of user *root* as they deal with filesystem mounts. Their source-code is available here in *s3fs* subfolder.
* Install the core toolset:
```
sudo make install WEBSVCUSER=cctv
```
* Configure AWS credentials:
  * Create file `/var/lib/cctv/.aws/credentials`:
```
sudo mkdir -p /var/lib/cctv/.aws && touch /var/lib/cctv/.aws/credentials
```
  * Add ACCESSKEY and SECRET of the user we've created in section 'Setup AWS Bucket' to the file (replace patterns with your info):
```
cat <<EOT >> /var/lib/cctv/.aws/credentials
[hk-aws-toolkit]
aws_access_key_id=XXXXXXXXXXXXXXXXXXXX
aws_secret_access_key=yyyyyyyyyyyyyyyyyyyyyyy+zzzzz+aaaaaaaaaa
EOT
```
 * Change permissions of the file so no other user in the system can access it:
```
sudo chmod -R 600 /var/lib/cctv/.aws && sudo chown -R cctv /var/lib/cctv/.aws
```
  **IMPORTANT NOTE:** The credentials are being stored on filesystem in plain-text. Linux OS provides sufficient protection of that data if you did it the way I described. By it remains very important that you use only designated user for this tool which we created in 'Setup AWS Bucket' section and **never** use root/admin account. Read article from Amazon if you want to know more on how to manage your access keys properly: https://docs.aws.amazon.com/accounts/latest/reference/credentials-access-keys-best-practices.html

## Using HK AWS Toolkit
### `hk-aws-tool.py` Tool
`hk-aws-tool.py` is the main and (so far) only tool for you to play with. You can do the following actions using the tool:
* See/list cameras and their corresponding data stored in S3
* Sort captured files into folders
* Purge old files [TODO]
* Archive files to Glacier FS (cheap long term storage)
* Run the WEB front-end

The command has help reference built-in which you invoke by calling:
```
hk-aws-tool.py -h
```

Main configuration file of the tool is available at `/etc/hkawstoolkit/config.yaml`. Among all options, pay your attention to the following:
* `aws.profile`: AWS profile name. Should match the one we created in `/var/lib/cctv/.aws/credentials` file
* `aws.cctv-bucket`: S3 Bucket name
* `aws.cctv-region`: AWS region where S3 Bucket is based in
* All paths are relative to the tool's data folder which is either `/usr/share/hkawstoolkit` by default or the one you've provided with `--wprefix` option. 

If you've correctly completed all the configuration we've listed here, you should get a list of cameras that data on S3 by issuing this command:
```
hk-aws-tool.py -a list-cameras
```
Example of the right output:
```
[rpavlyuk@server ~]$ hk-aws-tool.py -a list-cameras
INFO: hk-aws-toolkit version 1.0
INFO: More info here: https://github.com/rpavlyuk/hikvision-aws-toolkit
INFO: tool action to take: list-cameras
INFO: Cameras in bucket [my-video-surveillance]
INFO: Found credentials in shared credentials file: ~/.aws/credentials
INFO: Total rows affected: 11. Start position: -1
CAM-EXT-001
CAM-EXT-002
CAM-EXT-003
CAM-EXT-004
CAM-EXT-005
CAM-EXT-006
```
You can use option `--quiet | -q` if you want to get just the output itself. For example, for future automation. Example:
```
[rpavlyuk@server ~]$ hk-aws-tool.py -a list-cameras --quiet
CAM-EXT-001
CAM-EXT-002
CAM-EXT-003
CAM-EXT-004
CAM-EXT-005
CAM-EXT-006
```

### Sorting captured event images
Hikvision IP Camera drops all events images into one folder. For example, in case of the setup as it was shown in section '*Setup IP Cameras*' the camera will store all images in folder `/var/lib/cctv/storage/CAM-EXT-001` which corresponds to S3 path `my-video-surveillance:/CAM-EXT-001`. After some time the folder will contain thousands or even hundred of thousands of images which will make it completely unusable and non-browsable.

`hk-aws-tool.py` has special function to sort event images for all cameras or particular one. In this case sorting means placing those images into subfolder that corresponds to the particular date. Using the above mentioned example, all captured images from events that took place on Feb 24, 2022 will be moved to folder `2022-02-24`. Thus, the path will look like: `my-video-surveillance:/CAM-EXT-001/2022-02-24`

The examples for sorting command:
* For camera named `CAM-EXT-003`:
```
hk-aws-tool.py -a store-camera-files -m 'CAM-EXT-003'
```
* For all cameras:
```
hk-aws-tool.py -a store-all-files
```

Core installation of the tool (which you did in section *'Setup HK AWS Toolkit'*) already installed a scheduled task which will do sorting and storing every hours for all cameras. You can find it at `/etc/cron.d/hk-aws-tool-collect`. You may change the frequency of the sorting-n-storing, but the default settings (every hour) should be be pretty okay. Also, you may see that scheduling sorting command acts only for JPEG images by default. But if your camera is producing other type of files as the result of the triggered event (for example, MP4 video), you may add them as well:
```
10 */1 * * * cctv /usr/bin/hk-aws-tool.py -c /etc/hkawstoolkit/config.yaml -a store-all-files -p "*.jpg"
45 */1 * * * cctv /usr/bin/hk-aws-tool.py -c /etc/hkawstoolkit/config.yaml -a store-all-files -p "*.mp4"
```
The command runs on behalf of unprivileged user `cctv` and it is recommended to leave it that way.

### Purging the old files
Purging (removal) is not yet implemented is a **TODO** task. However, you can archive those images to S3 Glacier which extremely cheap storage and keep them there for a very long time. See the section below.

### Archiving files to deep storage
AWS Cloud provides the ability to use a very deep storage which is as cheaper as infrequent is access to it. AWS Glacier is that type of storage. 

The tool provides ability to archive certain sorted folders to S3 Glacier. For example, we have folder `my-video-surveillance:/CAM-EXT-001/2022-02-24/` with 250 `*.jpg` files in it. Archiving it folder will result that those files be moved to newly created archive `my-video-surveillance:/CAM-EXT-001/archive/2022-02-24.tar.gz` and its storage class will be set to GLACIER. Folder `my-video-surveillance:/CAM-EXT-001/2022-02-24/` is then removed.

Below are some example of how you do the archiving:
* Archive files from Dec 20, 2021 for camera `CAM-EXT-004`:
```
hk-aws-tool.py -a archive-camera-folder-on-date -m CAM-EXT-004 -d 2021-12-20
```
* Archive all files from December 2021 for camera `CAM-EXT-004`:
```
hk-aws-tool.py -a archive-camera-folder-pattern -m CAM-EXT-004 -p "*2021-12-*"
```
* Archive all files for all cameras from December 2021:
```
hk-aws-tool.py -a archive-all-by-pattern -p "*2021-12-*"
```
**NOTE**: Opening asterisk sign '*' is important at the beginning of the pattern.

Please, note some **important** things when using archiving function of the tool:
* Archive function works only with sorted files. See section *'Sorting captured event images'* for details. Sorting job is enabled by default, but if you disabled it -- archiving will not/may not work.
* Archiving generates S3 traffic and if you have huge amount of data, it may drive you bill up. Amazon Free Tier gives you 100Gb of free traffic which you may easily exceed. Beware of that.
* Due to the challenges above, archive function has a limitation of affected dates for archival set to 31. For example, it may potentially match 365 folders with sorted files if you set pattern to `*2021-*`, but only first 31 of them will be processed. This shold protect you from the archiver to affect terrabytes of data and thus running your montly bill to the sky. You can change that limitation in `config.yaml` by changing option `archive.batch_folder_limit` to some bigger value, but that's not recommended unless you know why.

### Viewing captured media via WEB client
The tools allows you to view captured images and other files via WEB client. WEB client is already being installaed as you install `hikvision-aws-toolkit`.

Please, consider some security options before you actually launch and start using the WEB:
* HK AWS Tool WEB Client was not built with the intend to be exposed publicly as the WEB service thus it is missing some important parts like authorization and authentication.
* Despite being a read-only type of software, the WEB client can still expose some valuable information, so it is solely your responsibility to place it behind the firewall and protect/secure the access to it.

Starting the WEB viewer is quite simple. Just start the corresponding `systemd` service:
```
sudo systemctl start hk-aws-web.service
```
Enable it if you want to have it starting on boot:
```
sudo systemctl enable hk-aws-web.service
```

The WEB client becomes available at http://127.0.0.1:8181/ or http://<your_ip>:8181/. The interface is quite primitive but at the same time quite useful if you want to browse the stored media.

## Additional Information

### What if the tool doesn't work for you?
If you see bug, defect or your are just facing the challenge using this tool -- drop me a message mailto:roman.pavlyuk@gmail.com and I will be happy to help.

Also, feel free to use GitHub's issue reporting tool to file anything you've found and anything that is bothering you.





  
