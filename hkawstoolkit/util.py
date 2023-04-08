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
import pprint
import json
import time
from operator import itemgetter

from pysondb import PysonDB

hk_cfg = dict()
hk_args = dict()

# Read configuration
def parse_config(args, config_file='/etc/hikvision/aws/config.yaml'):
    
    global hk_cfg, hk_args

    # Check if file exists
    if not os.path.isfile(config_file):
        logging.error("Oh nooo! The configuration file " + config_file + " cannot be found :(")
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), config_file)

    # Read the configuration
    logging.debug("Loading basic configuration from " + config_file)
    with open(config_file, 'r') as ymlfile:
        cfg = yaml.load(ymlfile, Loader=Loader)

    # globalize variables
    hk_cfg = cfg
    hk_args = args

    return cfg

#
# CACHE functions
#
def get_cache_db(cfg):
    global hk_args
    return PysonDB(hk_args.wprefix + "/" + cfg['db']['cache'])

def new_cache_object():

    return {
        'session_id': '0',
        'timestamp': time.time(),
        'path': '',
        'data': ''
    }

def put_cache_object(cfg, obj):
    cache_db = get_cache_db(cfg=cfg)
    return cache_db.add(obj)

def get_cache_object_by_id(cfg, id):
    cache_db = get_cache_db(cfg=cfg)
    return cache_db.get_by_id(
        id
    )

def get_cache_object_by_session_id(cfg, session_id):
    cache_db = get_cache_db(cfg=cfg)
    return cache_db.get_by_query(
        query=lambda x: x['session_id'] == session_id
    )

def get_cache_object_by_session_id_and_path(cfg, session_id, path):
    cache_db = get_cache_db(cfg=cfg)
    return cache_db.get_by_query(
        query=lambda x: x['session_id'] == session_id and x['path'] == path
    )

def get_cache_object_by_session_id_and_path_nonexp(cfg, session_id, path, exp_timestamp = time.time()):
    cache_db = get_cache_db(cfg=cfg)
    ret_list = cache_db.get_by_query(
        query=lambda x: x['session_id'] == session_id and x['path'] == path and x['timestamp'] >= exp_timestamp
    )
    if ret_list:
        new_ret_list = sorted(ret_list, key=lambda x: ret_list[x]['timestamp'], reverse=True)
        return new_ret_list
    
    return ret_list

#
# AWS Connectivity Functions
#
def get_aws_session(cfg):

    return boto3.Session(profile_name=cfg['aws']['profile'])

def get_aws_client(cfg):

    session = boto3.Session(profile_name=cfg['aws']['profile'])

    s3_client = session.client('s3')

    return s3_client


def get_aws_resource(cfg):
    
    session = boto3.Session(profile_name=cfg['aws']['profile'])

    s3_resource = session.resource('s3')

    return s3_resource   

def list_s3_objects(s3_client, bucket, pfx="", delimiter='/'):

    # ensure prefix has trailing slash
    if pfx != "":
        pfx.strip('/')
        pfx = pfx + "/"
    
    rsp = dict()

    rsp = s3_client.list_objects_v2(Bucket=bucket, Prefix=pfx, Delimiter=delimiter)     

    return rsp

#
# S3 Response Processing
#

# cleanup and process the result of S3 objects search and listing
def process_s3_listing(rsp, pfx = "", as_folders=False, all_objects = False, cached = False, session_id = '0', startPos = -1, sort_order = 'asc'):
    
    global hk_cfg

    fs_folders = []
    fs_files = []
    fs_objects = []
    ret_objects = []


    exp_timestamp = time.time() - hk_cfg['cache']['expire']
    # Try to find the request in cache
    c_objects = get_cache_object_by_session_id_and_path_nonexp(hk_cfg, session_id=session_id, path=pfx, exp_timestamp=exp_timestamp)
    if c_objects and cached:
        logging.info("Found objects in cache and cache is enabled. Session: " + session_id + ". Path: " + pfx + ". Count: " + str(len(c_objects)))
        if len(c_objects) > 0: 
            logging.info("Loading data from local cache.")              
            ret_objects = get_cache_object_by_id(hk_cfg, c_objects[0])['data']
    else: # either cache is disabled OR up2date folder content was not found in cache

        if not rsp.__contains__("Contents"):
            logging.warning("Response contains no 'Content' key")
            return []
        
        if all_objects:
            logging.debug("Extracting folder and files list from the response")
            if rsp.__contains__("CommonPrefixes"):
                logging.debug("Common prefixes found. Extracting.")
                fs_folders = list(obj["Prefix"] for obj in rsp["CommonPrefixes"])
            else:
                logging.debug("Common prefixes not found. Empty folders list to be added.")
                fs_folders = []
            logging.debug("Adding files to any folders found above.")
            fs_files = list(obj["Key"] for obj in rsp["Contents"])
        else:
            if as_folders:
                logging.debug("Extracting folder list from the response")
                if rsp.__contains__("CommonPrefixes"):
                    logging.debug("Common prefixes found. Extracting.")
                    fs_folders = list(obj["Prefix"] for obj in rsp["CommonPrefixes"])
                else:
                    logging.debug("Common prefixes not found. Empty folders list to be added.")
                    fs_folders = []
            else:
                logging.debug("Extracting files list from the response")
                fs_files = list(obj["Key"] for obj in rsp["Contents"])      
            
        fs_objects = fs_folders + fs_files

        for fs_object in fs_objects:
            ret_objects.append(fs_object.strip("/"))

        # If we loaded folder content from S3 and we have to deal with caching, 
        # it means that we have to save existing response to cache now
        if cached:
            logging.info("Object not cached yet. Session: " + session_id + ". Path: " + pfx + ".")
            c_obj = new_cache_object()
            c_obj['path'] = pfx
            c_obj['timestamp'] = time.time()
            c_obj['session_id'] = session_id
            c_obj['data'] = ret_objects
            put_cache_object(hk_cfg, c_obj)

    # Sort the list
    ret_objects.sort(reverse = True if sort_order == 'desc' else False)

    # Paging. If start position is bigger than 0, it means paging is enabled and should receive only part of the list
    total_affected_objects = len(ret_objects)
    logging.info("Total rows affected: " + str(total_affected_objects) + ". Start position: " + str(startPos) )
    if startPos >= 0:
        logging.info("Paging is enabled!")
        if (startPos + int(hk_cfg['web']['page_size'])) > total_affected_objects:
            logging.info("Extracting items from " + str(startPos) + " to the end of items list (" + str(total_affected_objects) + ")")
            ret_objects = ret_objects[startPos:]
        else:
            logging.info("Extracting items from " + str(startPos) + " to " + str(startPos+int(hk_cfg['web']['page_size'])))
            ret_objects = ret_objects[startPos:startPos+int(hk_cfg['web']['page_size'])]
        # Append the iformation of total object available so paginator on WEB can form the proper request
        ret_objects.append({ 'total_objects' : total_affected_objects})

    return ret_objects

# S3: list subfolders in S3 folder / bucket
def list_s3_subfolders(s3_client, bucket, pfx="", delimiter="/", session_id = '0'):

    rsp = list_s3_objects(s3_client, bucket, pfx, delimiter)
    return process_s3_listing(rsp, pfx = pfx, as_folders=True, session_id = session_id)

# S3: list subfolders in S3 folder / bucket filtered by pattern
def list_s3_subfolders_filtered(s3_client, bucket, pfx="", delimiter="/", pattern="*", session_id='0'):

    folders = list_s3_subfolders(s3_client, bucket, pfx=pfx, delimiter=delimiter, session_id = session_id)
    logging.debug(json.dumps(folders))
    return fnmatch.filter(folders, pattern)

# S3: list only files in the particular folder on S3
def list_s3_files(s3_client, bucket, pfx="", delimiter="/", session_id = '0'):

    rsp = list_s3_objects(s3_client, bucket, pfx, delimiter)
    return process_s3_listing(rsp, pfx = pfx, as_folders=False, session_id = session_id)

# S3: list all objects, folders and subfolders in S3 folder
def list_s3_folder(s3_client, bucket, pfx="", cached = False, session_id = '0', startPos = -1, sort_order = 'asc'):

    rsp = list_s3_objects(s3_client, bucket, pfx)
    return process_s3_listing(rsp, pfx = pfx, as_folders=False, all_objects = True, cached = cached, session_id = session_id, startPos = startPos, sort_order = sort_order)

# S3: list files in S3 folder but filter them using pattern (similar to shell pattern with *, ? )
def list_s3_files_filtered(s3_client, bucket, pfx="", delimiter="/", pattern="*", session_id = '0'):

    files = list_s3_files(s3_client, bucket, pfx, delimiter, session_id = session_id)
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

# S3: set object tagging
def set_s3_file_tagging(s3_client, bucket, object, tagging):

    put_tags_response = s3_client.put_object_tagging(
    Bucket=bucket,
    Key=object,    
    Tagging=tagging
    )

    return put_tags_response

# S3: set archive tags on the object
def set_s3_archive_tag(s3_client, bucket, object):

    tagging = {
        'TagSet': [
            {
                'Key': 'archived',
                'Value': 'yes'
            },
        ]
    }

    return set_s3_file_tagging(s3_client, bucket, object, tagging)

# S3: set object storage class
def set_s3_object_storage_class(s3_client, bucket, object, storage_class):

    logging.info("Changing storage class of object \"" + object + "\" to " + str(storage_class))

    copy_source = {
        'Bucket': bucket,
        'Key': object
    }

    s3_client.copy(
    copy_source, bucket, object,
    ExtraArgs = {
        'StorageClass': storage_class,
        'MetadataDirective': 'COPY'
    }
    )