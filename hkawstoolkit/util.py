"""Util package for hk-aws-toolkit"""

import logging, yaml
import os, errno

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import boto3

# Read configuration
def parse_config(args, config_file='/etc/hikvision/aws/config.yaml'):
    
    # Check if file exists
    if not os.path.isfile(config_file):
        logging.error("Oh nooo! The configuration file " + config_file + " cannot be found :(")
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), config_file)

    # Read the configuration
    logging.debug("Loading basic configuration from " + config_file)
    with open(config_file, 'r') as ymlfile:
        cfg = yaml.load(ymlfile, Loader=Loader)

    return cfg

def get_aws_client(cfg):

    session = boto3.Session(profile_name=cfg['aws']['profile'])

    s3_client = session.client('s3')

    return s3_client


def get_aws_resource(cfg):
    
    session = boto3.Session(profile_name=cfg['aws']['profile'])

    s3_resource = session.resource('s3')

    return s3_resource   


# get list of objects in "directory"
def list_s3_directory(s3_client, bucket, pfx=""):

    # ensure prefix has trailing slash
    if pfx != "":
        pfx.strip('/')
        pfx = pfx + "/"

    # new emptry files list
    files = []

    # get the directories/files in the "directory"
    paginator = s3_client.get_paginator('list_objects')
    result = paginator.paginate(Bucket=bucket, Delimiter='/', Prefix=pfx)
    for prefix in result.search('CommonPrefixes'):
        if not prefix:
            logging.debug("Got NULL prefix the getting directory list in list_s3_directory")
            break
        _filename = str(prefix.get('Prefix'))
        files.append(_filename.strip('/'))

    return files

def list_s3_directory_files(s3_resource, bucket, pfx=""):

    # ensure prefix has trailing slash
    if pfx != "":
        pfx.strip('/')
        pfx = pfx + "/"

    # new emptry files list
    files = [] 
    
    cctv_bucket = s3_resource.Bucket(bucket)

    for object_summary in cctv_bucket.objects.filter(Prefix=pfx):
        files.append(object_summary.key)

    return files