"""Util package for hk-aws-toolkit"""

import logging, yaml
import os, errno

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import boto3
import botocore

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

# S3: list subfolder in S3 folder / bucket
def list_s3_subfolders(s3_client, bucket, pfx="", delimiter="/"):

    rsp = list_s3_objects(s3_client, bucket, pfx, delimiter)
    return process_s3_listing(rsp, as_folders=True)

# S3: list only files in the particular folder on S3
def list_s3_files(s3_client, bucket, pfx="", delimiter="/"):

    rsp = list_s3_objects(s3_client, bucket, pfx, delimiter)
    return process_s3_listing(rsp, as_folders=False)

# S3: list all objects, folders and subfolders in S3 folder
def list_s3_folder(s3_client, bucket, pfx=""):

    rsp = list_s3_objects(s3_client, bucket, pfx)
    return process_s3_listing(rsp, as_folders=False)

# S3: list files in S3 folder but filter them using pattern (similar to shell pattern with *, ? )
def list_s3_files_filtered(s3_client, bucket, pfx="", delimiter="/", pattern="*"):

    files = list_s3_files(s3_client, bucket, pfx, delimiter)
    return fnmatch.filter(files, pattern)

# S3: check if folder exists and is not empty in S3
def folder_s3_exists_and_not_empty(s3_client, bucket, path):
    '''
    Folder should exists. 
    Folder should not be empty.
    '''
    if not path.endswith('/'):
        path = path+'/' 
    resp = s3_client.list_objects(Bucket=bucket, Prefix=path, Delimiter='/',MaxKeys=1)
    return 'Contents' in resp

# S3: check if folder exists; can be empty or not
def folder_s3_exists(s3_client, bucket, path):
    '''
    Folder should exists. 
    Folder could be empty.
    '''
    path = path.rstrip('/') 
    resp = s3_client.list_objects(Bucket=bucket, Prefix=path, Delimiter='/',MaxKeys=1)
    return 'CommonPrefixes' in resp

# S3: check if file exists
def file_s3_exists(s3_resource, bucket, file):
    try:
        s3_resource.Object(bucket, file).load()
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            # The object does not exist.
            logging.debug("Object \"" + str(file) + "\" doesn't exists")
            return False
        else:
            # Something else has gone wrong.
            logging.error("Something went wrong when checking if object \"" + str(file) + "\" exists")
            return False
    else:
        # The object does exist.
        logging.debug("Object \"" + str(file) + "\" exists")
        return True
        
    return

# S3: copy file within the bucket
def copy_s3_file(s3_resource, bucket, src_object, dest_object):
    logging.debug("Copying file \"" + str(src_object) + "\" as \"" + str(dest_object) + "\"")
    s3_resource.Object(bucket, dest_object).copy_from(CopySource=bucket+"/"+src_object)
    return s3_resource.Object(bucket, dest_object)

# S3: copy file within the bucket to specified folder
def copy_s3_file_to_folder(s3_resource, bucket, src_object, dest_folder):
    logging.debug("Copying file \"" + str(src_object) + "\" to folder \"" + str(dest_folder) + "\"")
    return copy_s3_file(s3_resource, bucket, src_object, dest_folder + "/" + os.path.basename(src_object))

# S3: delete the file / object (incl folder)
def delete_s3_file(s3_resource, bucket, dest_object):
    logging.debug("Removing file \"" + str(dest_object) + "\"")
    s3_resource.Object(bucket, dest_object).delete()
    return  

# S3: move file within the bucket
# NOTE: Destination folder doesn't have to exist and will be created by API
def move_s3_file(s3_resource, bucket, src_object, dest_object):
    logging.debug("Moving file \"" + str(src_object) + "\" as \"" + str(dest_object) + "\"")
    # Copy object A as object B
    obj = copy_s3_file(s3_resource, bucket, src_object, dest_object)
    # Delete the former object A
    delete_s3_file(s3_resource, bucket, src_object)

    return obj

# S3: move file within the bucket to specified folder
 # NOTE: Destination folder doesn't have to exist and will be created by API
def move_s3_file_to_folder(s3_resource, bucket, src_object, dest_folder):
    logging.debug("Moving file \"" + str(src_object) + "\" to folder \"" + str(dest_folder) + "\"")
    return move_s3_file(s3_resource, bucket, src_object, dest_folder + "/" + os.path.basename(src_object))

# S3: get object's last modification date/time
def get_s3_object_modified_date(s3_resource, bucket, object):

    return s3_resource.Object(bucket, object).last_modified

# S3: get a name of the folder that is the date target file was created
def get_s3_modification_date_folder(s3_resource, bucket, object):

    return get_s3_object_modified_date(s3_resource, bucket, object).strftime("%Y-%m-%d")