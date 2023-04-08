
import logging, os
from urllib.parse import urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from hkawstoolkit import util

from PIL import Image
from io import BytesIO
import pprint
import uuid

from flask import Flask
from flask import request
from flask import make_response
from flask import render_template, send_from_directory, session

hkawsweb = Flask(__name__)


@hkawsweb.route("/static/<resource>/<filename>")
def send_static(resource, filename):
    folder = util.hk_args.wprefix + "/" + util.hk_cfg['web']['dirs']['root'] + "/" + resource
    logging.info("Serving static "+ resource + " file \"" + filename + "\" from folder \"" + folder + "\"")
    return send_from_directory(folder, filename)

@hkawsweb.route("/", methods=['GET'])
def act_index():

    # check/set/update session cookies
    if '_hk_aws_sid' in session:
        session_id = str(session.get('_hk_aws_sid'))
        logging.info("WEB Session ID found: " + session_id)
    else:
        session_id = str(uuid.uuid4())
        session['_hk_aws_sid'] = session_id
        logging.info("Starting new WEB session: " + session_id)

    # Start building response
    main_response = ""

    object = request.args.get('object', "")
    if object == "/":
        object = ""
    content = request.args.get('content', "list")
    thumb = request.args.get('thumb', "no")
    startPos = int(request.args.get('startPos', 0))
    sortOrder = request.args.get('sortOrder', util.hk_cfg['web']['sort'])

    logging.info("Object: " + str(object) + ", content: " + str(content)+ ", thumb: " + str(thumb))

    s3_client = util.get_aws_client(util.hk_cfg)
    s3_resource = util.get_aws_resource(util.hk_cfg)

    if content == "raw":
        logging.info("Rendering raw file content: " + object)
        f_obj = s3_resource.Object(util.hk_cfg['aws']['cctv_bucket'], object)
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
        tpl_file = util.hk_args.wprefix + "/" + util.hk_cfg['web']['dirs']['templates'] + "/content_list.html"
        template = open(tpl_file, 'rb').read()

        # get directory listing
        s_list = "<span><a href=\"/?object=/\">[ ROOT ]</a></span><br/>"
        s_list += "<span><a href=\"/?object=" + os.path.dirname(object) + "\"> [ .. ]</a></span><br/>"
            
        file_objects = util.list_s3_folder(s3_client, util.hk_cfg['aws']['cctv_bucket'], object, cached = True, session_id = session_id, startPos = startPos, sort_order=sortOrder)
        
        total_objs_in_folder = len(file_objects)
        logging.info("web: total items in folders/files/info list received: " + str(total_objs_in_folder))
        # check of the there's information about total objects in the folder (since we may have just one page returned here)
        # and pop it from the list if it's there, correcting the value of 'total_objs_in_folder' varialbe
        if len(file_objects) > 0:
            if type(file_objects[-1]) is dict:
                if 'total_objects' in file_objects[-1]:
                    total_objs_in_folder = file_objects.pop()['total_objects']
                    logging.info("web: found total_objects record in returned folder list. Adjusting totals to: " + str(total_objs_in_folder))

        # Form the list of objects (folders and files) on WEB
        for l_obj in file_objects:
            if str(l_obj) == str(object):
                continue
            
            if util.folder_s3_exists(s3_client, util.hk_cfg['aws']['cctv_bucket'], l_obj):
                s_list += "<span><a href=\"/?object=" + str(l_obj) + "\">" + os.path.basename(str(l_obj)) +"</a></span><br/>"

            if util.file_s3_exists(s3_resource, util.hk_cfg['aws']['cctv_bucket'], l_obj):
                f_obj = s3_resource.Object(util.hk_cfg['aws']['cctv_bucket'], l_obj)
                if not f_obj.content_type == "image/jpeg":
                    s_list += "<span><a href=\"/?object=" + l_obj + "\">" + os.path.basename(str(l_obj)) +"</a></span><br/>"
                else:
                    s_list += "<div class=\"cell-img\"><a href=\"/?object=" + l_obj + "&content=raw\"><img src=\"/?object=" + l_obj + "&content=raw&thumb=yes\" /></a></div>"

        if total_objs_in_folder > int(util.hk_cfg['web']['page_size']):
            logging.info("web: total objects in this folder is " + str(total_objs_in_folder) + " which is bigger than page size (" + str(util.hk_cfg['web']['page_size']) + "). Paginator will displayed.")
            pager = "<div> <strong>Navigate:</strong> "
            if (startPos - int(util.hk_cfg['web']['page_size'])) > 0:
                pager += "<span><a href=\"/?object=" + str(object) + "&startPos=" + str(startPos - int(util.hk_cfg['web']['page_size'])) + "\"> << Previous</a></span> |"
            elif (startPos - int(util.hk_cfg['web']['page_size'])) <= 0 and (startPos - int(util.hk_cfg['web']['page_size'])) > (-1)*int(util.hk_cfg['web']['page_size']):
                pager += "<span><a href=\"/?object=" + str(object) + "&startPos=0\"> << Previous</a></span> |"
            
            if (total_objs_in_folder - startPos) > int(util.hk_cfg['web']['page_size']):
                pager += "| <span><a href=\"/?object=" + str(object) + "&startPos=" + str(startPos + int(util.hk_cfg['web']['page_size'])) + "\"> Next >> </a></span>"
            
            pager += "</div>"
        else:
            logging.info("web: total objects in this folder is " + str(total_objs_in_folder) + " which is lower than page size (" + str(util.hk_cfg['web']['page_size']) + "). No Paginator will be displayed.")
            pager = ""

        # Sorter
        sorter = "<div><strong>Sort:</strong> <span><a href=\"/?object=" + str(object) + "&startPos=" + str(startPos) + "&sortOrder=asc\">^ Ascending </a></span>"
        sorter += "| <span><a href=\"/?object=" + str(object) + "&startPos=" + str(startPos) + "&sortOrder=desc\">v Descending </a></span></div>"

        # Insert data in template
        # TODO: switch to render_template() from fask
        template = template.replace(b'{TITLE}', bytes(object,'UTF-8'))
        template = template.replace(b'{PATH}', bytes(str(object) + "/",'UTF-8'))
        template = template.replace(b'{MEDIA_LIST}', bytes(s_list,'UTF-8'))
        template = template.replace(b'{TOTAL_OBJECTS}', bytes(str(total_objs_in_folder),'UTF-8'))
        template = template.replace(b'{PAGER}', bytes(pager,'UTF-8'))
        template = template.replace(b'{SORTORDER}', bytes(sorter,'UTF-8'))
        template = template.replace(b'{SHOWING_OBJECTS}', bytes(str(len(file_objects)),'UTF-8'))
        template = template.replace(b'{SHOWING_FROM}', bytes(str(startPos+1),'UTF-8'))
        template = template.replace(b'{SHOWING_TO}', bytes(str(startPos + int(util.hk_cfg['web']['page_size']) if startPos+int(util.hk_cfg['web']['page_size']) <= total_objs_in_folder else total_objs_in_folder),'UTF-8'))

        resp = make_response(template)
        resp.headers['Content-Type'] = "text/html"
        return resp


    return "<p>NoOP!</p>"

def a_web(args, cfg):
    util.hk_cfg = cfg
    util.hk_args = args
    logging.warning("Built-in server is not intended for production use. Please, ensure that this WEB server is not publicly exposed!")
    hkawsweb.secret_key = 'a7fe43c0-d57c-11ed-9cf5-43d5756e1d6c'
    hkawsweb.run(host=cfg['web']['host'], port=cfg['web']['port'], debug=args.verbose)

    return
