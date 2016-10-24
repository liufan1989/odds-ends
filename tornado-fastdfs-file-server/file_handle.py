#!/usr/bin/python
#-*- encoding:utf-8 -*-
import tornado.web 
import tornado.gen
from tornado.concurrent import run_on_executor
from concurrent.futures import ThreadPoolExecutor
from postprocess import *
from error_code import *

def getRemoteSessionId(userid,sessionid):
    pass

def HttpResponse(request,errorcode,extendmsg=""):
    request.set_header ('Result',str(errorcode))
    if errorcode != 0:
        request.write(RESULT_CODE[errorcode] + "\r\n" + extendmsg)

class FileHandler(tornado.web.RequestHandler):
    executor = ThreadPoolExecutor(1024)
    filenamepatt1 = re.compile(r'\d{11}@\d{9}\..+')
    filenamepatt2 = re.compile(r'picture\d{2}\..+')
    filenamepatt3 = re.compile(r'icon_user\d{2}\..+')
    filenamepatt4 = re.compile(r'\d{18}\..+')
    usernamepatt1 = re.compile(r'\d{11}')

    @run_on_executor
    def postprocess(self,arg):
        db = self.application.database
        logging.info('postprocess....................')
        filetype = arg.get('filetype','')
        if 'callback' in FileTypeMapTable[filetype]:
            return FileTypeMapTable[filetype]['callback'](db,arg)
        logging.info(filetype+':no postprocess')

    @run_on_executor
    def checkvalid(self,userid,sessionid,filetype):
        if 'checksession' in FileTypeMapTable[filetype]:
            if not FileTypeMapTable[filetype]['checksession']:
                logging.info(str(filetype) + ' no need check session') 
                return True 
        db = self.application.database
        return db.checkSessionInfo(userid,sessionid)

    def checkusernamepattern(self,username,filetype):
        if 'usernamecheck' in FileTypeMapTable[filetype]:
            if not FileTypeMapTable[filetype]['usernamecheck']:
                logging.info(str(filetype) + ' no need check username') 
                return True 
        m = self.usernamepatt1.match(username)
        if m:
            return True
        else:
            return False

    def checkfilenamepattern(self,filename):
        return True
        if filename == '':
            return False
        m1 = self.filenamepatt1.match(filename) 
        m2 = self.filenamepatt2.match(filename)
        m3 = self.filenamepatt3.match(filename)
        m4 = self.filenamepatt4.match(filename)
        if m1 or m2 or m3 or m4:
            return True
        else:
            return False
        
    def genfilepath(self,arg):
        username = arg.get('username','')
        filename = arg.get('filename','')
        filetype = arg.get('filetype','')
        mode = arg.get('mode','')
        if username == ''  or filename == '' or filetype == '':
            return ''
        filepath = FilePath(username,filetype,mode,filename)
        return filepath

    @run_on_executor
    def download(self,arg):
        username = arg.get('username','')
        filename = arg.get('filename','')
        filetype = arg.get('filetype','')
        mode = arg.get('mode','')

        if not self.checkusernamepattern(username,filetype):
            logging.info('checkusernamepattern fail:%s' % username)
            return 1002
        if not self.checkfilenamepattern(filename):
            logging.info('checkfilenamepattern fail:%s' % filename)
            return 1003
        if filetype not in FileTypeMapTable:
            return 1004

        filepath = FilePath(username,filetype,mode,filename)
        if filepath == '':
            return 1006
        logging.info("Path:" + filepath)
        if not os.path.exists(filepath):
            return 1005
        self.set_header ('Content-Type', 'application/octet-stream')
        self.set_header ('Content-Disposition', 'attachment; filename=%s' % filename)
        self.set_header ('Content-Length',os.path.getsize(filepath))
        with open(filepath, 'rb') as f:
            data = f.read()
            self.write(data)
        return 0

    @run_on_executor
    def upload(self,arg):
        username = arg.get('username','')
        filename = arg.get('filename','')
        filetype = arg.get('filetype','')
        mode = arg.get('mode','')
        md5code = arg.get('md5',0)
        filecontent = arg.get('filecontent','')

        if filetype not in FileTypeMapTable:
            return 1004

        if not self.checkusernamepattern(username,filetype):
            logging.info('checkusernamepattern fail:%s' % username)
            return 1002

        if not self.checkfilenamepattern(filename):
            logging.info('checkfilenamepattern fail:%s' % filename)
            return 1003

        if not checkfilecontentpattern(filename,filetype,filecontent):
            logging.info('checkfilecontentpattern fail:%s' % filename)
            return 1009

        filepath = FilePath(username,filetype,mode,filename)
        if filepath == '':
            return 1006

        logging.info("Path:" + filepath)
        if not os.path.exists(os.path.dirname(filepath)):
            os.makedirs(os.path.dirname(filepath))
        f = open(filepath,'wb')
        f.write(filecontent)
        f.close()
        if check_md5(filecontent,md5code):
            return 0
        return 1007

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        try:
            arg = {}
            arg['userid'] = self.request.headers.get('userid','')
            arg['sessionid'] = self.request.headers.get('sessionid','')

            arg['username'] = self.request.headers.get('username','')
            arg['filename'] = self.get_argument('filename','').encode('utf-8')
            arg['filetype'] = self.get_argument('filetype','')
            arg['mode'] = self.get_argument('mode','')
            logging.info("%s,%s,%s" % (self.request.headers.get("X-Real-Ip",""),"FileHandler",str(arg)))

            if arg['filetype'] not in FileTypeMapTable:
                HttpResponse(self,1004,"download fail!!!")
                self.finish()
                return
            auth = yield self.checkvalid(arg['userid'],arg['sessionid'],arg['filetype'])
            if not auth:
                HttpResponse(self,1001,"download fail!!!")
                self.finish()
                return
            flag = yield self.download(arg)
            if flag != 0: 
                HttpResponse(self,flag,"download fail!!!")
            else:
                HttpResponse(self,0)
            self.finish()
        except Exception as e:
            logging.info(traceback.format_exc())
            self.clear()
            HttpResponse(self,9999)
            self.finish()

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def post(self):
        try:
            arg = {}
            arg['userid'] = self.request.headers.get('userid','')
            arg['sessionid'] = self.request.headers.get('sessionid','')

            arg['username'] = self.request.headers.get('username','')
            arg['filename'] = self.get_argument('filename','').encode('utf-8')
            arg['filetype'] = self.get_argument('filetype','')
            arg['mode']  = self.get_argument('mode','')
            arg['md5'] = self.request.headers.get('md5',0)
            logging.info("%s,%s,%s" % (self.request.headers.get("X-Real-Ip",""),"FileHandler",str(arg)))
            arg['filecontent'] = self.request.body
            if arg['filetype'] not in FileTypeMapTable:
                HttpResponse(self,1004,"upload fail!!!")
                self.finish()
                return
            auth = yield self.checkvalid(arg['userid'],arg['sessionid'],arg['filetype'])
            if not auth:
                HttpResponse(self,1001,"upload fail!!!")
                self.finish()
                return
            flag = yield self.upload(arg)
            if flag == 0:
                yield self.postprocess(arg)
                HttpResponse(self,flag,"upload ok!!!")
            else:
                HttpResponse(self,flag,"upload fail!!!")
            self.finish()
        except Exception as e:
            logging.info(traceback.format_exc())
            self.clear()
            HttpResponse(self,9999)
            self.finish()
