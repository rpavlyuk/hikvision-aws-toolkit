"""Util package for hk-aws-toolkit"""

import logging, yaml
import os, errno

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import boto3

import fnmatch

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

def list_s3_objects(s3_client, bucket, pfx="", delimiter="/"):

    # ensure prefix has trailing slash
    if pfx != "":
        pfx.strip('/')
        pfx = pfx + "/"

    rsp = s3_client.list_objects_v2(Bucket=bucket, Prefix=pfx, Delimiter=delimiter)

    return rsp

# cleanup and process the result of S3 objects search and listing
def process_s3_listing(rsp, as_folders=False):
    if not rsp.__contains__("Contents"):
        return []
    if as_folders:
        fs_objects = list(obj["Prefix"] for obj in rsp["CommonPrefixes"])
    else:
        fs_objects = list(obj["Key"] for obj in rsp["Contents"])
    ret_objects = []
    for fs_object in fs_objects:
        ret_objects.append(fs_object.strip("/"))
    return ret_objects


def list_s3_subfolders(s3_client, bucket, pfx="", delimiter="/"):

    rsp = list_s3_objects(s3_client, bucket, pfx, delimiter)
    return process_s3_listing(rsp, as_folders=True)

def list_s3_files(s3_client, bucket, pfx="", delimiter="/"):

    rsp = list_s3_objects(s3_client, bucket, pfx, delimiter)
    return process_s3_listing(rsp, as_folders=False)

def list_s3_folder(s3_client, bucket, pfx=""):

    rsp = list_s3_objects(s3_client, bucket, pfx)
    return process_s3_listing(rsp, as_folders=False)

def list_s3_files_filtered(s3_client, bucket, pfx="", delimiter="/", pattern="*"):

    files = list_s3_files(s3_client, bucket, pfx, delimiter)
    return fnmatch.filter(files, pattern)