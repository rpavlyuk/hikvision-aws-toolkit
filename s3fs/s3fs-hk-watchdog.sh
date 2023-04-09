#!/bin/bash
#
# s3fs-watchdog.sh
#
# Run from the root user's crontab to keep an eye on s3fs which should always
# be mounted.
#
# Note:  If getting the amazon S3 credentials from environment variables
#   these must be entered in the actual crontab file (otherwise use one
#   of the s3fs other ways of getting credentials).
#
# Example:  To run it once every minute getting credentials from envrironment
# variables enter this via "sudo crontab -e":
#
#   AWSACCESSKEYID=XXXXXXXXXXXXXX
#   AWSSECRETACCESSKEY=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
#   * * * * * /root/s3fs-watchdog.sh
#

NAME=s3fs
BUCKET=pvl-video-surveillance
MOUNTPATH=/media/VL1_MOVIES/security/storage
MOUNT=/bin/mount
UMOUNT=/bin/umount
GREP=/bin/grep
PS=/bin/ps
NOP=/bin/true
DATE=/bin/date
MAIL=/bin/mail
LOGGER=/usr/bin/logger
RM=/bin/rm
TOUCH=/usr/bin/touch
TESTFILE=test.io

# Checking the process
$PS -ef|$GREP -v grep|$GREP $NAME|grep $BUCKET >/dev/null 2>&1

# Trying to put the file in s3fs mounted folder
[ $? -eq 0 ] && $TOUCH $MOUNTPATH/$TESTFILE >/dev/null 2>&1

# Act depending on how the operation with the file went
case "$?" in
   0)
   # It is running in this case so we do nothing.
   $NOP
   ;;
   1)
   echo "$NAME is NOT RUNNING for bucket $BUCKET. Remounting $BUCKET with $NAME and sending notices."
   $UMOUNT --force $MOUNTPATH >/dev/null 2>&1
   $MOUNT -o nonempty $MOUNTPATH >/tmp/watchdogmount.out 2>&1
   NOTICE=/tmp/watchdog.txt
   echo "$NAME for $BUCKET was not running and was started on `$DATE`" > $NOTICE
   $LOGGER -p local0.warning -t $NAME "$NOTICE"
   $RM -f $NOTICE
   ;;
esac

exit
