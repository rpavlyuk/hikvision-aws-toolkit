
import logging, os
from urllib.parse import urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from hkawstoolkit import util

from PIL import Image
from io import BytesIO


from flask import Flask
from flask import request
from flask import make_response
from flask import render_template, send_from_directory

hkawsweb = Flask(__name__)

hk_cfg = dict()
hk_args = dict()


@hkawsweb.route("/static/<resource>/<filename>")
def send_css(resource, filename):
    folder = hk_args.wprefix + "/" + hk_cfg['web']['dirs']['root'] + "/" + resource
    logging.info("serving static "+ resource + " file \"" + filename + "\" from folder \"" + folder + "\"")
    return send_from_directory(folder, filename)

@hkawsweb.route("/", methods=['GET'])
def act_index():

    global hk_cfg
    global hk_args

    main_response = ""

    object = request.args.get('object', "")
    if object == "/":
        object = ""
    content = request.args.get('content', "list")
    thumb = request.args.get('thumb', "no")

    logging.info("Object: " + str(object) + ", content: " + str(content)+ ", thumb: " + str(thumb))

    s3_client = util.get_aws_client(hk_cfg)
    s3_resource = util.get_aws_resource(hk_cfg)

    if content == "raw":
        logging.info("Rendering raw file content: " + object)
        f_obj = s3_resource.Object(hk_cfg['aws']['cctv_bucket'], object)
        img = f_obj.get()['Body'].read()

        if thumb == "yes":
            p_image = Image.open(BytesIO(img))
            p_image.thumbnail((400,300))
            img_file = BytesIO()
            p_image.save(img_file, format="JPEG")
            main_response = img_file.getvalue()
        else:
            main_response = img

        resp = make_response(main_response)
        resp.headers['Content-Type'] = "image/jpeg"
        return resp

    elif content == "list":
        # Render template: load it from file and parse variables
        tpl_file = hk_args.wprefix + "/" + hk_cfg['web']['dirs']['templates'] + "/content_list.html"
        template = open(tpl_file, 'rb').read()

        # get directory listing
        s_list = "<span><a href=\"/?object=/\">[ ROOT ]</a></span><br/>"
        s_list += "<span><a href=\"/?object=" + os.path.dirname(object) + "\"> [ .. ]</a></span><br/>"
        dir_objects = util.list_s3_subfolders(s3_client, hk_cfg['aws']['cctv_bucket'], object)
        for l_obj in dir_objects:
            if str(l_obj) == str(object):
                continue
            s_list += "<span><a href=\"/?object=" + l_obj + "\">" + os.path.basename(str(l_obj)) +"</a></span><br/>"       
        file_objects = util.list_s3_files(s3_client, hk_cfg['aws']['cctv_bucket'], object)
        for l_obj in file_objects:
            if str(l_obj) == str(object):
                continue
            
            if util.file_s3_exists(s3_resource, hk_cfg['aws']['cctv_bucket'], l_obj):
                f_obj = s3_resource.Object(hk_cfg['aws']['cctv_bucket'], l_obj)
                if not f_obj.content_type == "image/jpeg":
                    s_list += "<span><a href=\"/?object=" + l_obj + "\">" + os.path.basename(str(l_obj)) +"</a></span><br/>"
                else:
                    s_list += "<div class=\"cell-img\"><a href=\"/?object=" + l_obj + "&content=raw\"><img src=\"/?object=" + l_obj + "&content=raw&thumb=yes\" /></a></div>"

        # Insert data in template
        # TODO: switch to render_template() from fask
        template = template.replace(b'{TITLE}', bytes(object,'UTF-8'))
        template = template.replace(b'{PATH}', bytes(object,'UTF-8'))
        template = template.replace(b'{MEDIA_LIST}', bytes(s_list,'UTF-8'))
        template = template.replace(b'{TOTAL_OBJECTS}', bytes(str(len(dir_objects)+len(file_objects)-1),'UTF-8'))

        resp = make_response(template)
        resp.headers['Content-Type'] = "text/html"
        return resp


    return "<p>NoOP!</p>"

def a_web(args, cfg):

    global hk_cfg, hk_args

    hk_cfg = cfg
    hk_args = args
    hkawsweb.run(port=cfg['web']['port'], debug=args.verbose)

    return