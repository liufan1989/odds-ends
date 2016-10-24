#!/usr/bin/python
#-*- encoding:utf-8 -*-
import tornado.web 
import tornado.gen
from tornado.concurrent import run_on_executor
from concurrent.futures import ThreadPoolExecutor
import traceback
import logging

from utils import *
from postprocess import *

#import FDFSPythonClient
#fastfdfscontext = FDFSPythonClient.fdfs_init("./fdfspythonclient.conf",1);

class FastFDFSHandler(tornado.web.RequestHandler):
    executor = ThreadPoolExecutor(1024)
    
    def get(self):
        logging.info("download through nginx server not tornado server !")

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def post(self):
        try:
            userid = self.request.headers.get('userid','')
            sessionid = self.request.headers.get('sessionid','')

            fileinfo = []

            filenum = int(self.get_argument('file_num',1))
            logging.info(self.request.arguments)

            logging.info("filenum:%d"%filenum)

	        #filename = self.get_argument('file1_name')
            #logging.info(filename)
		

            for x in range(filenum):
                filename = self.get_argument('file%d_name'%x)
                filepath = self.get_argument('file%d_path'%x)
                ftype = self.get_argument('file%d_content_type'%x)
                fsize = self.get_argument('file%d_size'%x)
                fmd5 = self.get_argument('file%d_md5'%x)

                logging.info('=================================')
                logging.info(filename)
                logging.info(filepath)
                logging.info(ftype)
                logging.info(fsize)
                logging.info(fmd5)
                logging.info('=================================')

                fileinfo.append({'filename':filename,'filepath':filepath,'ftype':ftype,'fsize':str(fsize),'fmd5':str(fmd5)})

            db = self.application.database
            groupidlist = yield fastfdfs_postprocess(self,db,fileinfo)

            for gid in groupidlist:
                self.set_header(gid[0],gid[1])

            self.set_header ('Result','0')
            self.write('upload ok')
            self.finish()

        except Exception as e:
            logging.info(traceback.format_exc())
            self.set_header ('Result','9999')
            self.write('fastfdfs handler process error')
            self.finish()
