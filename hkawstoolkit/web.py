
import logging, os
from urllib.parse import urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from hkawstoolkit import util

from PIL import Image
from io import BytesIO

class HTTP_HK_AWS_Handler(BaseHTTPRequestHandler):
    
    cfg = None
    args = None

    content_type = "text/html"

    @staticmethod
    def set_cfg(cfg):
        HTTP_HK_AWS_Handler.cfg = cfg
    
    @staticmethod
    def set_args(args):
        HTTP_HK_AWS_Handler.args = args

    
    def _set_headers(self):
        self.send_response(200)
        self.send_header("Content-type", self.content_type)
        self.end_headers()

    def _html(self, message):
        """This just generates an HTML document that includes `message`
        in the body. Override, or re-write this do do more interesting stuff.
        """

        content = f"<html><body><h1>{message}</h1></body></html>"
        return content.encode("utf8")  # NOTE: must return a bytes object!

    def do_GET(self):

        if not HTTP_HK_AWS_Handler.cfg or not HTTP_HK_AWS_Handler.args:
            logging.error("App configuration for request handler has not been initialized. Cannot serve")
            return

        # Object (folder or file) to display
        object = ""
        content = "list"
        thumb = "no"
        query_components = dict()

        main_response = ""

        # Parse request parameters
        query = urlparse(self.path).query
        if not len(query) < 1:
            query_components = dict(qc.split("=") for qc in query.split("&"))
        
        # Fill in object param
        if not query_components.__contains__("object"):
            object = ""
        else:
            object = str(query_components['object'])
            object = object.strip('/')
        
        if not query_components.__contains__("content"):
            content = "list"
        else:
            content = str(query_components['content'])

        if not query_components.__contains__("thumb"):
            thumb = "no"
        else:
            thumb = str(query_components['thumb'])

        logging.info("Object: " + str(object) + ", content: " + str(content)+ ", thumb: " + str(thumb))

        s3_client = util.get_aws_client(HTTP_HK_AWS_Handler.cfg)
        s3_resource = util.get_aws_resource(HTTP_HK_AWS_Handler.cfg)

        if content == "raw":
            logging.info("Rendering raw file content: " + object)
            f_obj = s3_resource.Object(HTTP_HK_AWS_Handler.cfg['aws']['cctv_bucket'], object)
            img = f_obj.get()['Body'].read()
            self.content_type = "image/jpeg"

            if thumb == "yes":
                p_image = Image.open(BytesIO(img))
                p_image.thumbnail((400,300))
                img_file = BytesIO()
                p_image.save(img_file, format="JPEG")
                main_response = img_file.getvalue()
            else:
                main_response = img

        elif content == "list":
            # Render template: load it from file and parse variables
            tpl_file = HTTP_HK_AWS_Handler.args.wprefix + "/" + HTTP_HK_AWS_Handler.cfg['web']['dirs']['templates'] + "/content_list.html"
            template = open(tpl_file, 'rb').read()

            # get directory listing
            s_list = "<span><a href=\"/?object=/\">[ ROOT ]</a></span><br/>"
            s_list += "<span><a href=\"/?object=" + os.path.dirname(object) + "\"> [ .. ]</a></span><br/>"
            dir_objects = util.list_s3_subfolders(s3_client, HTTP_HK_AWS_Handler.cfg['aws']['cctv_bucket'], object)
            for l_obj in dir_objects:
                if str(l_obj) == str(object):
                    # s_list += "<span><a href=\"/?object=" + l_obj + "\">[ . ]</a></span><br/>" 
                    continue
                s_list += "<span><a href=\"/?object=" + l_obj + "\">" + os.path.basename(str(l_obj)) +"</a></span><br/>"       
            file_objects = util.list_s3_files(s3_client, HTTP_HK_AWS_Handler.cfg['aws']['cctv_bucket'], object)
            for l_obj in file_objects:
                if str(l_obj) == str(object):
                    # s_list += "<span><a href=\"/?object=" + l_obj + "\">[ . ]</a></span><br/>" 
                    continue
                
                if util.file_s3_exists(s3_resource, HTTP_HK_AWS_Handler.cfg['aws']['cctv_bucket'], l_obj):
                    f_obj = s3_resource.Object(HTTP_HK_AWS_Handler.cfg['aws']['cctv_bucket'], l_obj)
                    if not f_obj.content_type == "image/jpeg":
                        s_list += "<span><a href=\"/?object=" + l_obj + "\">" + os.path.basename(str(l_obj)) +"</a></span><br/>"
                    else:
                        s_list += "<span style=\"margin: 3px;\"><a href=\"/?object=" + l_obj + "&content=raw\"><img src=\"/?object=" + l_obj + "&content=raw&thumb=yes\" /></a></span>"

            # Insert data in template
            template = template.replace(b'{TITLE}', bytes(object,'UTF-8'))
            template = template.replace(b'{PATH}', bytes(object,'UTF-8'))
            template = template.replace(b'{MEDIA_LIST}', bytes(s_list,'UTF-8'))

            main_response = template

        # Send the response 
        self._set_headers()
        self.wfile.write(main_response)

    def do_HEAD(self):
        self._set_headers()

    def do_POST(self):
        # Doesn't do anything with posted data
        self._set_headers()
        self.wfile.write(self._html("POST!"))

def a_web(args, cfg):
    
    HTTP_HK_AWS_Handler.set_cfg(cfg)
    HTTP_HK_AWS_Handler.set_args(args)
    run(cfg, handler_class=HTTP_HK_AWS_Handler)

    return

def run(cfg, server_class=HTTPServer, handler_class=BaseHTTPRequestHandler): 
    logging.info("Starting AWS HK starage WEB browser") 
    server_address = ('', cfg['web']['port'])
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()