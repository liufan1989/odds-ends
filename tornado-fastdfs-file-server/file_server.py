#!/usr/bin/python
#-*- encoding:utf-8 -*-

from tornado.concurrent import run_on_executor
from tornado.options import define, options

import tornado.httpserver
import tornado.ioloop
import threading

from file_handle import *
from fastdfs_file_server import *
from db_api import *
from constants import *

################################################################
####conf args
define("port"  ,default=7777, help="File Server run on port : 7777", type=int)
define('debug' ,default=True, help='enable debug mode')
define('config',default='./fileserver.conf')

define('redishost',default='127.0.0.1')
define('redisport',default=6379,type=int)
define('redisdb',default=0,type=int)

define('mysqlhost',default='127.0.0.1')
define('mysqlport',default=3306, type=int)
define('mysqldb',default='express')
define('mysqluser',default='root')
define('mysqlpasswd',default='123456')

define('resource_root',default='/srv/liufan/resource')
define('topic_root',default='/topic')
################################################################
#####main.py
class Application(tornado.web.Application):
    def __init__(self,config):
        handlers=[
            (r"/resource", FileHandler),
        ]
        logging.info('Application init...........')
        self.database = DataBase(config)
        tornado.web.Application.__init__(self, handlers, debug=True)
        #tornado.web.Application.__init__(self, handlers)

if __name__ == '__main__':
    tornado.options.parse_command_line()
    tornado.options.parse_config_file(options.config,False)
    GlobalVar.resource_root = options['resource_root']
    GlobalVar.topic_root = options['topic_root']
    logging.info("File Root Path:%s" % GlobalVar.resource_root)
    logging.info("Server Running in Port:%s" % options.port)
    logging.info(threading.current_thread())
    app = Application(options)
    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()
