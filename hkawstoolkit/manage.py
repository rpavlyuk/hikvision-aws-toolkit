
from multiprocessing.spawn import import_main_path
from hkawstoolkit import util
import logging

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

    if args.camera == None:
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

    if args.camera == None:
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
    if args.camera == None or args.date == None:
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