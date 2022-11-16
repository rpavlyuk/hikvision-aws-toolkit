
from multiprocessing.spawn import import_main_path
from hkawstoolkit import util
import logging
import os

from s3_tar import S3Tar

import pprint

def action(args, cfg):

    if args.action == 'cleanup':
        cleanup_all(args, cfg)
    elif args.action == 'upload':
        upload_all(args, cfg)
    elif args.action == 'list-cameras':
        a_list_cameras(args, cfg)
    elif args.action == 'list-camera-dirs':
        a_list_camera_directory(args, cfg, args.camera)
    elif args.action == 'list-camera-files':
        a_list_camera_files(args, cfg, args.camera, args.pattern)
    elif args.action == 'list-camera-files-on-date':
        a_list_camera_files_on_date(args, cfg, args.camera, args.date, args.pattern)
    elif args.action == 'store-camera-files':
        a_store_camera_files(args, cfg, args.camera, args.pattern)
    elif args.action == 'store-all-files':
        a_store_all_files(args, cfg, args.pattern)
    elif args.action == 'archive-camera-folder-on-date':
        a_archive_camera_date_folder(args, cfg, args.camera, args.date)
    elif args.action == 'archive-camera-folder-pattern':
        a_archive_camera_pattern_folder(args, cfg, args.camera, args.pattern)
    else:
        logging.warn("Unknown action provided: " + args.action)
    


def get_all_cameras(args, cfg):

    # aws client
    s3_client = util.get_aws_client(cfg)

    cameras_list = util.list_s3_subfolders(s3_client, cfg['aws']['cctv_bucket'])

    return cameras_list

def a_list_cameras(args, cfg):

    logging.info("Cameras in bucket [" + cfg['aws']['cctv_bucket'] + "]")

    for cam in get_all_cameras(args, cfg):
        print(str(cam))

    return

def a_list_camera_directory(args, cfg, camera):

    if camera == None:
        logging.critical("Camera option is needed for this action")
        return

    # aws client
    s3_client = util.get_aws_client(cfg)

    logging.info("Directories for camera [" + camera + "]")

    # arch_directories = util.list_s3_directory(s3_client, cfg['aws']['cctv_bucket'], pfx=camera)
    arch_directories = util.list_s3_subfolders(s3_client, cfg['aws']['cctv_bucket'], pfx=camera)

    
    logging.info("Found total " + str(len(arch_directories)) + " objects for camera " + camera)

    for dir in arch_directories:
        print(str(dir))   
    
    return

def a_list_camera_files(args, cfg, camera, pattern="*"):

    if camera == None:
        logging.critical("Camera option is needed for this action")
        return

    # aws client
    s3_client = util.get_aws_client(cfg)
    
    logging.info("Files for camera [" + camera + "]")

    arch_files = util.list_s3_files_filtered(s3_client, cfg['aws']['cctv_bucket'], pfx=camera, pattern=pattern)

    logging.info("Found total " + str(len(arch_files)) + " objects for camera " + camera)

    for file in arch_files:
        print(str(file))  

    return 

def a_list_camera_files_on_date(args, cfg, camera, date, pattern="*"):
    if camera == None or date == None:
        logging.critical("Camera and/or date options is needed for this action")
        return  
    
    # aws client
    s3_client = util.get_aws_client(cfg)

    logging.info("Files for camera [" + camera + "] on date " + str(date))

    arch_files = util.list_s3_files_filtered(s3_client, cfg['aws']['cctv_bucket'], pfx=str(camera)+"/"+str(date), pattern=pattern)

    logging.info("Found total " + str(len(arch_files)) + " objects for camera " + camera)

    for file in arch_files:
        print(str(file))  

    return 

def a_store_camera_files(args, cfg, camera, pattern="*"):

    if camera == None:
        logging.critical("Camera option is needed for this action")
        return

    logging.info("Storing files (" + str(pattern) + ") for camera " + str(camera))
    # aws client
    s3_client = util.get_aws_client(cfg)
    s3_resource = util.get_aws_resource(cfg)
    cam_files = util.list_s3_files_filtered(s3_client, cfg['aws']['cctv_bucket'], pfx=camera, pattern=pattern)
    logging.info("Found " + str(len(cam_files)) + " non-stored objects for camera " + camera)

    for file in cam_files:
        logging.info("Processing file \"" + str(file) + "\"")
        if not util.file_s3_exists(s3_resource, cfg['aws']['cctv_bucket'], file):
            logging.info("Object \"" + str(file) + "\" doesn't exists or is not a file. Skipping now.")
            continue
        m_folder = util.get_s3_modification_date_folder(s3_resource, cfg['aws']['cctv_bucket'], file)
        obj = util.move_s3_file_to_folder(s3_resource, cfg['aws']['cctv_bucket'], file, str(camera) + "/" + m_folder)
        logging.info("File stored as \"" + obj.key + "\"")

    return

def a_store_all_files(args, cfg, pattern="*"):

    logging.info("Processing files (" + str(pattern) +") for all cameras in bucket [" + cfg['aws']['cctv_bucket'] + "]")

    for cam in get_all_cameras(args, cfg):
        a_store_camera_files(args, cfg, cam, pattern)

    return

def a_archive_camera_date_folder(args, cfg, camera, date):
    if camera == None or date == None:
        logging.critical("Camera and/or date options is needed for this action")
        return 

    s3_client = util.get_aws_client(cfg)
    s3_resource = util.get_aws_resource(cfg)
    prefix_path = camera + "/" + date
    if not util.folder_s3_exists_and_not_empty(s3_client, cfg['aws']['cctv_bucket'], prefix_path):
        logging.error("Target folder to archive \"" + prefix_path + "\" doesn't exist or is empty.")
        return

    arch_file = camera + "/archive/" + date + "." + cfg['archive']['extension']

    job = S3Tar(
        cfg['aws']['cctv_bucket'],
        arch_file,  # Use `tar.gz` or `tar.bz2` to enable compression
        # target_bucket=None,  # Default: source bucket. Can be used to save the archive into a different bucket
        # min_file_size='50MB',  # Default: None. The min size to make each tar file [B,KB,MB,GB,TB]. If set, a number will be added to each file name
        # save_metadata=False,  # If True, and the file has metadata, save a file with the same name using the suffix of `.metadata.json`
        remove_keys=True,  # If True, will delete s3 files after the tar is created
    
        # ADVANCED USAGE
        allow_dups=True,  # When False, will raise ValueError if a file will overwrite another in the tar file, set to True to ignore
        # cache_size=5,  # Default 5. Number of files to hold in memory to be processed
        # s3_max_retries=4,  # Default is 4. This value is passed into boto3.client's s3 botocore config as the `max_attempts`
        # part_size_multiplier=10,  # is multiplied by 5 MB to find how large each part that gets upload should be
        session=util.get_aws_session(cfg),  # For custom aws session
    )
    
    job.add_files(
        prefix_path + "/",
        folder=prefix_path,  # If a folder is set, then all files from this directory will be added into that folder in the tar file
        # preserve_paths=False,  # If True, it will use the dir paths relative to the input path inside the tar file
    )

    # Start the tar'ing job after files have been added
    job.tar()

    # Set archive tags
    logging.info("Tagging file \"" + arch_file + "\" as archive")
    util.set_s3_archive_tag(s3_client, cfg['aws']['cctv_bucket'], arch_file)

    # Move to Glacier
    if cfg['archive']['glacier']:
        util.set_s3_object_storage_class(s3_client, cfg['aws']['cctv_bucket'], arch_file, 'GLACIER')

    # Remove folder
    util.delete_s3_file(s3_resource, cfg['aws']['cctv_bucket'], prefix_path + "/")

    return

def a_archive_camera_pattern_folder(args, cfg, camera, pattern):

    if camera == None:
        logging.critical("Camera option is needed for this action")
        return

    # aws client
    s3_client = util.get_aws_client(cfg)

    logging.info("Directories for camera [" + camera + "] to be archived")

    arch_directories = util.list_s3_subfolders_filtered(s3_client, cfg['aws']['cctv_bucket'], pfx=camera, pattern=pattern)
    
    logging.info("Found total " + str(len(arch_directories)) + " objects for camera \"" + camera + "\" matching pattern (" + pattern + ")")

    # protect against archive batches being too big
    if len(arch_directories) > cfg['archive']['batch_folder_limit']:
        logging.error("Number of folders found is bigger than limit (" + str(cfg['archive']['batch_folder_limit']) + "). Please, correct the search pattern and try again.")
        return

    for date_folder in arch_directories:
        arch_date = os.path.basename(date_folder)
        logging.info("Archiving folder \"" + arch_date + "\" for camera \"" + camera + "\"")
        a_archive_camera_date_folder(args, cfg, camera, arch_date)

    return


def cleanup_all(args, cfg):
    # get all cameras
    logging.info("Getting all camera directories from bucket " + cfg['aws']['cctv_bucket'])
    cameras = get_all_cameras(args, cfg)

    # cleanup per each camera
    for camera in cameras:
        cleanup_camera(args, cfg, camera, cfg['archive']['keep_files_days'])

def cleanup_camera(args, cfg, camera, keep_days = 365):

    # aws client
    s3_client = util.get_aws_client(cfg)

    logging.info("Running cleanup for camera " + camera)

    arch_directories = util.list_s3_directory(s3_client, cfg['aws']['cctv_bucket'], pfx=camera)
    logging.info("Found total " + str(len(arch_directories)) + " objects for camera " + camera)

    pprint.pprint(arch_directories)


def upload_all(args, cfg):
    # aws client
    s3_client = util.get_aws_client(cfg)