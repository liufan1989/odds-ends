#!/usr/bin/python
#-*- encoding:utf-8 -*-
import tornado.httpserver
import tornado.ioloop
import tornado.options 
import tornado.web 
import tornado.gen
from tornado.concurrent import run_on_executor
from tornado.concurrent import Future
from tornado.options import define, options
from concurrent.futures import ThreadPoolExecutor
from DBUtils.PooledDB import PooledDB
from MySQLdb.cursors import DictCursor
import MySQLdb
import redis
import logging
import shutil
import os
import PIL.Image as Image
import pdb
import traceback
import hashlib
import subprocess as sp
import re
import uuid
import threading
import json
import urllib2
import datetime
import time
import random
import magic

define("port"  ,default=7777, help="BiaoDa File Server run on port : 7777", type=int)
define('debug' ,default=True, help='enable debug mode')
define('config',default='./biaodafileserver.conf')

define('redishost',default='127.0.0.1')
define('redisport',default=6379,type=int)
define('redisdb',default=0,type=int)

define('mysqlhost',default='127.0.0.1')
define('mysqlport',default=3306, type=int)
define('mysqldb',default='express')
define('mysqluser',default='root')
define('mysqlpasswd',default='123456')

define('resource_root',default='/srv/biaoda/resource')
################################################################
###Error Code
RESULT_CODE = {
    0:"success",
    1001:"auth fail",
    1002:"username illegal",
    1003:"filename illegal",
    1004:"filetype illegal",
    1005:"file not exsit",
    1006:"path error",
    1007:"md5 fail",
    1008:"postprocess fail",
    1009:"filecontent illegal",
    9999:"Server error,please contact developers of tomoon,thanks!",
}
################################################################
###utils.py

def get_file_md5(full_path):
    """
    获取文件MD5
    :param full_path: 文件绝对路径
    :return: 全小写MD5
    """
    f = open(full_path, 'rb')
    content = f.read()
    f.close()
    md5 = hashlib.md5(content).hexdigest()
    return md5.lower()

def get_image_info(full_path):
    """
    获取图片相关信息
    :param full_path: 音频文件绝对路径
    :return: 字节大小, MD5, 图片宽度, 图片高度
    """
    size = os.path.getsize(full_path)
    md5 = get_file_md5(full_path)
    img = Image.open(full_path)
    width, height = img.size
    img.fp.close()
    return size, md5, width, height

'''
Duration: 00:00:05.78, start: 0.000000, bitrate: 8680 kb/s
Stream #0:0(eng): Video: h264 (Baseline) (avc1 / 0x31637661), yuv420p, 1280x720, 7782 kb/s, ... 30.13 fps ...
'''
reg_resolution = "^\s*Stream.*,\s*(\d+)x(\d+),"
reg_duration = "^\s*Duration:\s*(\d+):(\d+):(\d+).(\d+),"
reg_rotate = "^\s*rotate\s*:\s*(\d+)"
re_resolution = re.compile(reg_resolution)
re_duration = re.compile(reg_duration)
re_rotate = re.compile(reg_rotate)

def get_video_info(full_path):
    """
    获取视频相关信息
    :param full_path: 视频文件绝对路径
    :return: 字节大小, MD5, 视频宽度, 视频高度, 视频时长
    """
    size = os.path.getsize(full_path)
    md5 = get_file_md5(full_path)
    width, height, duration = 0, 0, 0
    rotate = 0

    (si, so, se) = os.popen3('ffmpeg -i "%s"' % full_path)
    lines = se.readlines()  # ffmpeg 如果参数没有指定输出文件, 则以错误的形式输出相关信息, stderr
    for line in lines:
        result = re_resolution.findall(line)
        for c in result:
            width, height = c[0], c[1]

        result = re_duration.findall(line)
        for c in result:
            hour, minute, second, micro_second = int(c[0]), int(c[1]), int(c[2]), int(c[3])
            duration = second + minute * 60 + hour * 3600

        result = re_rotate.findall(line)
        for c in result:
            rotate = int(c)

    if rotate == 90:
        width, height = height, width

    si.close()
    so.close()
    se.close()
    return size, md5, width, height, duration

'''
Duration: 00:04:05.66, start: 0.025056, bitrate: 338 kb/s
Stream #0:0: Audio: mp3, 44100 Hz, stereo, s16p, 320 kb/s
Stream #0:1: Video: mjpeg, yuvj444p(pc, bt470bg/unknown/unknown), 640x640 [SAR 72:72 DAR 1:1], 90k tbr, 90k tbn, 90k tbc
'''
# reg_duration = "^\s*Duration:\s*(\d+):(\d+):(\d+).(\d+),"  # 与视频文件相同

def get_voice_info(full_path):
    """
    获取音频相关信息
    :param full_path: 音频文件绝对路径
    :return: 字节大小, MD5, 音频时长
    """
    size = os.path.getsize(full_path)
    md5 = get_file_md5(full_path)
    duration = 0

    (si, so, se) = os.popen3('ffmpeg -i "%s"' % full_path)
    lines = se.readlines()
    for line in lines:
        result = re_duration.findall(line)
        for c in result:
            hour, minute, second, micro_second = int(c[0]), int(c[1]), int(c[2]), int(c[3])
            duration = second + minute * 60 + hour * 3600
    si.close()
    so.close()
    se.close()
    return size, md5, duration

def VideoFirstFrame(srcfile,dstpath):
    sp.call(['ffmpeg', '-i', srcfile, '-ss', '0', '-vframes', '1', '-f', 'image2', '-y', dstpath],close_fds=True)

def videosnapshot(srcpath):
    srcdir = srcpath[0:srcpath.rfind('/')]
    dstpath = srcdir.replace("video","snapshot")
    if not os.path.exists(dstpath):
        os.makedirs(dstpath)
    dstfile = os.path.basename(srcpath).split(".")[0]
    dstpath = dstpath + '/' + dstfile
    VideoFirstFrame(srcpath,dstpath)    

def check_md5(filecontent,md5code):
    filehash = hashlib.md5()
    filehash.update(filecontent)
    hexdig = filehash.hexdigest()
    logging.info("client_md5:%s,server_md5:%s" % (md5code,hexdig))
    if hexdig == md5code:
        return True
    else:
        return False 

def getRemoteSessionId(userid,sessionid):
    pass

def HttpResponse(request,errorcode,extendmsg=""):
    request.set_header ('Result',str(errorcode))
    if errorcode != 0:
        request.write(RESULT_CODE[errorcode] + "\r\n" + extendmsg)

##################################################################
####database.py

class handler(object):
    def insertone(self):
        pass
    def insertmany(self):
        pass
    def selectone(self):
        pass
    def selectmany(self):
        pass
    def commit(self):
        pass
    def rollback(self):
        pass
    def over(self):
        pass

class Mysql(handler):

    def __init__(self,pool):
        self._conn = pool.connection()
        self._cursor = self._conn.cursor()

    def insertone(self,sql,value=None):
        return self._cursor.execute(sql,value)

    def insertmany(self,sql,value=None):
        return self._cursor.executemany(sql,value)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()
    #pooled connections __del__ method while auto return conn to pool
    #no need to be called by hand if necessary
    def over(self):
        self._cursor.close()
        self._conn.close()

class Redis(handler):
    def __init__(self,pool):
        self._conn = redis.StrictRedis(connection_pool=pool)
        self._pipe = self._conn.pipeline()

    def insertone(self,key,value):
        self._pipe.set(key,value)

    def insertmany(self,values):
        if isinstance(values,dict):  
            for (key,val) in values:
                self._pipe.set(key,val)
        else:
            raise TypeError('redis insertmany error')

    def selectone(self,key):
        self._pipe.get(key)
        return self._pipe.execute()[0]

    def selectmany(self,keylist):
       if isinstance(keylist, list):
           self._pipe.mget(keylist) 
           return self._pipe.execute()
       else:
           raise TypeError('redis selectmany error')
        
    def selecthashone(self,key,field=None):
        if field is None:
            self._pipe.hgetall(key)
        else:
            self._pipe.hget(key,field)
        return self._pipe.execute()[0]

    def inserthashone(self,key,field,value):
        self._pipe.hset(key,field,value)

    def inserthashmany(self,key,values):
        if isinstance(values,dict):
            self._pipe.hmset(key,values)
        else:
            raise TypeError('redis inserthashmany error')

    def commit(self):
        self._pipe.execute()

    def rollback(self):
        pass
    
    #BasePipeline __del__ method while auto return conn to pool
    #no need to be called by hand if necessary
    def over(self):
        self._pipe.reset()
   
    

#singleton: this is not singleton
class context(object):
    def __init__(self,config):
        logging.info('context init.................')
        self.redis_pool = redis.ConnectionPool(host=config['redishost'], port=config['redisport'], db=config['redisdb'])

        #PooledDB __del__ realese all conn
        self.mysql_pool = PooledDB(creator=MySQLdb, mincached=5, maxcached=20,
                    host=config['mysqlhost'], port=config['mysqlport'], user=config['mysqluser'],
                    passwd=config['mysqlpasswd'],db=config['mysqldb'], use_unicode=False, charset='utf8mb4',
                    cursorclass=DictCursor)

    def connectionhandler(self,conntype):
        if conntype == 'mysql':
            return Mysql(self.mysql_pool)
        elif conntype == 'redis':
            return Redis(self.redis_pool)
        else:
            raise TypeError('context get connection handler error')

    def __del__(self):
        self.redis_pool.disconnect()
        self.mysql_pool.close()
    


class dbengine(context):
    def __init__(self,config):
        logging.info('dbengine init.................')
        super(dbengine,self).__init__(config)

    def addSessionInfo(self,values):
        logging.info('addSessionInfo.................')
        try:
            redisConn = self.connectionhandler('redis')
            logging.info(redisConn)            
            redisConn.insertone(values['key'],values['value'])
            redisConn.commit()
        except:
            logging.info('addSessionInfo exception................')
            redisConn.rollback()
            logging.info(str(values))
            raise

    def getSessionInfo(self,values):
        logging.info('getSessionInfo.................')
        try:
            redisConn = self.connectionhandler('redis')
            logging.info(redisConn)            
            res = redisConn.selectone(values['key'])
            return res
        except:
            logging.info('getSessionInfo exception................')
            logging.info(str(values))
            raise

    def addShareFileInfo(self,values):
        logging.info('addShareFileInfo........')
        try:
            logging.info('mysql conn..................')
            mysqlConn = self.connectionhandler('mysql')
            logging.info(mysqlConn)            
            sql = "insert into share_files_info\
            (user_id,file_name,file_md5,node_id,file_type,file_size,pixel_width,pixel_height,duration,create_time) \
             values (%(user_id)s, %(file_name)s, %(file_md5)s,\
            %(node_id)s, %(file_type)s, %(file_size)s, %(pixel_width)s, %(pixel_height)s, %(duration)s, NOW())"
            res = mysqlConn.insertone(sql, values)
            mysqlConn.commit()
        except:
            logging.info('addShareFileInfo exception................')
            mysqlConn.rollback()
            raise

    def addMsgFileInfo(self,values):
        logging.info('addMsgFileInfo........')
        try:
            logging.info('mysql conn..................')
            mysqlConn = self.connectionhandler('mysql')
            logging.info(mysqlConn)            
            sql = "insert into message_files_info\
            (user_id,file_name,file_md5,node_id,file_type,file_size,pixel_width,pixel_height,duration,create_time) \
             values (%(user_id)s, %(file_name)s, %(file_md5)s,\
            %(node_id)s, %(file_type)s, %(file_size)s, %(pixel_width)s, %(pixel_height)s, %(duration)s, NOW())"
            res = mysqlConn.insertone(sql, values)
            mysqlConn.commit()
        except:
            logging.info('addMsgFileInfo exception................')
            mysqlConn.rollback()
            raise

    def addAvatarFileInfo(self,values):
        logging.info('addAvatarFileInfo........')
        try:
            logging.info('mysql conn..................')
            mysqlConn = self.connectionhandler('mysql')
            logging.info(mysqlConn)            
            sql = "insert into avatar_files_info\
            (user_id,file_name,file_md5,node_id,file_size,pixel_width,pixel_height,create_time) \
             values (%(user_id)s, %(file_name)s, %(file_md5)s,\
            %(node_id)s, %(file_size)s, %(pixel_width)s, %(pixel_height)s, NOW())"
            res = mysqlConn.insertone(sql, values)
            mysqlConn.commit()
        except:
            logging.info('addAvatarFileInfo exception................')
            mysqlConn.rollback()
            raise

    def addBgPicFileInfo(self,values):
        logging.info('addBgPicFileInfo........')
        try:
            logging.info('mysql conn..................')
            mysqlConn = self.connectionhandler('mysql')
            logging.info(mysqlConn)            
            sql = "insert into bg_pic\
            (user_id,file_name,file_md5,node_id,file_size,pixel_width,pixel_height,create_time) \
             values (%(user_id)s, %(file_name)s, %(file_md5)s, "\
            "%(node_id)s, %(file_size)s, %(pixel_width)s, %(pixel_height)s, NOW())"
            res = mysqlConn.insertone(sql, values)
            mysqlConn.commit()
        except:
            logging.info('addBgPicFileInfo exception................')
            mysqlConn.rollback()
            raise

class DataBase(object):
    def __init__(self,config=None):
        logging.info('DataBase init.................')
        self.dbengine = dbengine(config)

    def checkSessionInfo(self,userid,sessionid):
        sid = self.dbengine.getSessionInfo(userid)
        if sid == sessionid:
            return True
        else:
            remotesid = getRemoteSessionId(userid,sessionid) 
            self.dbengine.addSessionInfo(userid,remotesid)
            if remotesid == sessionid:
                return True
            else:
                return False

    def saveimageinformation(self,srcpath,username,filename,bizFrom):
        size, md5, width, height = get_image_info(srcpath)
        d = {'user_id':username,'file_name':filename,'file_md5':md5,\
             'node_id':'','file_type':1,'file_size':size,\
             'pixel_width':width,'pixel_height':height,'duration':0}
        if 'msg' == bizFrom:
            self.dbengine.addMsgFileInfo(d)
        else:
            self.dbengine.addShareFileInfo(d)

    def savevideoinformation(self,srcpath,username,filename,bizFrom):
        size, md5, width, height, duration = get_video_info(srcpath);
        d = {'user_id':username,'file_name':filename,'file_md5':md5,\
             'node_id':'','file_type':3,'file_size':size,\
             'pixel_width':width,'pixel_height':height,'duration':duration}
        if 'msg' == bizFrom:
            self.dbengine.addMsgFileInfo(d)
        else:
            self.dbengine.addShareFileInfo(d)

    def savevoiceinformation(self,srcpath,username,filename,bizFrom):
        size, md5, duration = get_voice_info(srcpath);
        d = {'user_id':username,'file_name':filename,'file_md5':md5,\
             'node_id':'','file_type':2,'file_size':size,\
             'pixel_width':0,'pixel_height':0,'duration':duration}
        if 'msg' == bizFrom:
            self.dbengine.addMsgFileInfo(d)
        else:
            self.dbengine.addShareFileInfo(d)

    def saveavatarbkgbicinformation(self,srcpath,username,filename,bizFrom):
        size, md5, width, height = get_image_info(srcpath);
        d = {'user_id':username,'file_name':filename,'file_md5':md5,\
             'node_id':'','file_size':size,\
             'pixel_width':width,'pixel_height':height}
        if bizFrom == 'avatar':
            self.dbengine.addAvatarFileInfo(d)
        else:
            self.dbengine.addBgPicFileInfo(d)

##################################################################
###utils.py
def ImageCompress(src,dst,maxpix):
    try:
        img = Image.open(src)
        orgw,orgh = img.size
        if orgw <= maxpix and orgh <= maxpix:
            neww = orgw
            newh = orgh
        elif orgh >= orgw and orgh > maxpix:
            newh = maxpix
            neww = maxpix * orgw / orgh
        elif orgw > orgh and orgw >= maxpix:
            neww = maxpix
            newh = maxpix * orgh / orgw
        else:
            pass
        logging.info("[%s]:[W:%s][H:%s]===>[W:%s][H:%s]" % (dst,orgw,orgh,neww,newh))
        img.resize((neww,newh), Image.ANTIALIAS).convert("RGB").save(dst, "jpeg")
    except:
        if 'img' in locals():
            img.fp.close()
        raise

def ClipResizeImg(**args):
    pass

def WaterMark(**args):
    pass 

def ImageSizeCompress(original,small=None,smallsize=120,mid=None,midsize=720):
    if small != None:
        smalldir = os.path.dirname(small)
        if not os.path.exists(smalldir):
            os.makedirs(smalldir)
        ImageCompress(original,small,smallsize)
    if mid != None:
        middir = os.path.dirname(mid)
        if not os.path.exists(middir):
            os.makedirs(middir)
        ImageCompress(original,mid,midsize)

FileFilterMapTable = ['JPEG','GIF','PNG','bitmap','RIFF','Adaptive Multi-Rate Codec','MPEG v4']

def checkfilecontentpattern(filename,ftype,filecontent):
    if len(filecontent) == 0:
        logging.info('%s is empty file'%filename)
        return False
    ft = magic.from_buffer(filecontent)
    logging.info('%s : %s'%(filename,ft))
    for x in FileFilterMapTable:
        if ft.find(x) != -1: 
            return True
    return False 
##################################################################
#postprocess.py
def ImageProcess(database,arg):
    username = arg.get('username','')
    filename = arg.get('filename','')
    filetype = arg.get('filetype','')
    mode = arg.get('mode','')
    bizFrom = arg.get('bizFrom','')
    srcpath = FilePath(username,filetype,mode,filename)
    smallpath = srcpath.replace('original','small')
    midpath = srcpath.replace('original','mid')
    logging.info("ImageProcess:%s" % srcpath)
    logging.info("ImageProcess:%s" % midpath)
    logging.info("ImageProcess:%s" % smallpath)
    # 话题里的图片会压缩中图和小图，头像和消息里的图片只会压缩小图
    if 'image' == filetype:
        ImageSizeCompress(srcpath,small=smallpath,mid=midpath)
    else:
        ImageSizeCompress(srcpath,small=smallpath,smallsize=260)
    # 获取图片的信息并存入数据库
    database.saveimageinformation(srcpath,username,filename,bizFrom)

def NewsProcess(database,arg):
    username = arg.get('username','')
    filename = arg.get('filename','')
    filetype = arg.get('filetype','')
    mode = arg.get('mode','')
    srcpath = FilePath(username,filetype,mode,filename)
    smallpath = srcpath.replace('original','small')
    midpath = srcpath.replace('original','mid')
    logging.info("NewsProcess:%s" % srcpath)
    logging.info("NewsProcess:%s" % midpath)
    logging.info("NewsProcess:%s" % smallpath)
    # news的图片会压缩中图和小图
    ImageSizeCompress(srcpath,small=smallpath,mid=midpath)

def VideoProcess(database,arg):
    username = arg.get('username','')
    filename = arg.get('filename','')
    filetype = arg.get('filetype','')
    mode = arg.get('mode','')
    bizFrom = arg.get('bizFrom','')
    srcpath = FilePath(username,filetype,mode,filename)
    logging.info("VideoProcess:%s" % srcpath)
    videosnapshot(srcpath)
    # 获取视频的信息并存入数据库
    database.savevideoinformation(srcpath,username,filename,bizFrom)

def VoiceProcess(database,arg):
    username = arg.get('username','')
    filename = arg.get('filename','')
    filetype = arg.get('filetype','')
    mode = arg.get('mode','')
    bizFrom = arg.get('bizFrom','')
    srcpath = FilePath(username,filetype,mode,filename)
    logging.info("VoiceProcess:%s" % srcpath)
    videosnapshot(srcpath)
    # 获取语音的信息并存入数据库
    database.savevoiceinformation(srcpath,username,filename,bizFrom)

def AvatarProcess(database,arg):
    username = arg.get('username','')
    filename = arg.get('filename','')
    filetype = arg.get('filetype','')
    mode = arg.get('mode','')
    srcpath = FilePath(username,filetype,mode,filename)
    smallpath = srcpath.replace('original','small')
    logging.info("AvatarProcess:%s" % srcpath)
    ImageSizeCompress(srcpath,small=smallpath,smallsize=120)
    # 获取头像图片的信息并存入数据库
    database.saveavatarbkgbicinformation(srcpath,username,filename,'avatar')


def BgPicProcess(database,arg):
    username = arg.get('username','')
    filename = arg.get('filename','')
    filetype = arg.get('filetype','')
    mode = arg.get('mode','')
    srcpath = FilePath(username,filetype,mode,filename)
    logging.info("BgPicProcess:%s" % srcpath)
    # 获取背景图片的信息并存入数据库
    database.saveavatarbkgbicinformation(srcpath,username,filename,'backgroundpic')

def MsgProcess(database,arg):
    username = arg.get('username','')
    filename = arg.get('filename','')
    filetype = arg.get('filetype','')
    mode = arg.get('mode','')
    srcpath = FilePath(username,filetype,mode,filename)
    logging.info("MsgProcess:%s" % srcpath)
    arg['bizFrom'] = 'msg'
    if 'video' == mode:
        VideoProcess(database,arg)
    if 'image' == mode:
        ImageProcess(database,arg)
    if 'voice' == mode:
        VoiceProcess(database,arg)


#############################################################
####new  api
resource_root = "/srv/biaoda/resource"
topic_root = "/share_file"
#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
def ImagePath(user,ftype,mode,filename):
    return resource_root + topic_root + '/' + user + '/' + mode + '/' + filename
def VideoPath(user,ftype,mode,filename):
    return resource_root + topic_root + '/' + user + '/' + 'video' + '/' + filename
def SnapshotPath(user,ftype,mode,filename):
    return resource_root + topic_root + '/' + user + '/' + 'snapshot' + '/' + filename
def VoicePath(user,ftype,mode,filename):
    return resource_root + topic_root + '/' + user + '/' + 'voice' + '/' + filename
def ChatPath(user,ftype,mode,filename):
    chatbasepath = resource_root + '/'  + 'chat' + '/' + user + '/' + mode + '/'
    if mode == 'image':
        return chatbasepath + 'original' + '/' +  filename
    else:
        return chatbasepath + filename
def AvatarPath(user,ftype,mode,filename):
    avatarbasepath = resource_root + '/' + 'avatar' + '/' 
    if mode == 'default':
        return avatarbasepath + 'default'  + '/' + filename
    else:
        return avatarbasepath + user +  '/' + mode + '/' + filename
def BgPicPath(user,ftype,mode,filename):
    bgpicbasepath = resource_root + '/' + 'backgroundpic' + '/' 
    if mode == 'default':
        return bgpicbasepath + 'default'  + '/' + filename
    else:
        return bgpicbasepath + user + '/' + filename    
def OfficialPath(user,ftype,mode,filename):
    return resource_root + '/' + 'official' + '/' + filename
def NewsPath(user,ftype,mode,filename):
    return resource_root + '/' + 'news' + '/' + mode + '/' + filename
#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$


FileTypeMapTable = {
                'image'        :{'path':'/image/','pathfunc':ImagePath,'mode':['original','mid','small'],'callback':ImageProcess},
                'video'        :{'path':'/video/','pathfunc':VideoPath,'callback':VideoProcess},
                'voice'        :{'path':'/voice/','pathfunc':VoicePath,'callback':VoiceProcess},
                'chat'         :{'path':'/chat/' ,'pathfunc':ChatPath,'mode':['image','video','voice','snapshot'],'callback':MsgProcess},
                'official'     :{'path':'/official/','pathfunc':OfficialPath,'usernamecheck':False},
                'avatar'       :{'path':'/avatar/','pathfunc':AvatarPath,'mode':['default','original','small'],'callback':AvatarProcess},
                'backgroundpic':{'path':'/backgroundpic/','pathfunc':BgPicPath,'mode':['default'],'callback':BgPicProcess},
                'snapshot'     :{'path':'/snapshot/','pathfunc':SnapshotPath},
                'news'         :{'path':'/news/','pathfunc':NewsPath,'mode':['original','mid','small'],'callback':NewsProcess,'checksession':False,'usernamecheck':False},
                }

def FilePath(user,ftype,mode,filename): 
    if filename == '':
        return ''
    if ftype not in FileTypeMapTable:
        return ''
    if ('mode' not in FileTypeMapTable[ftype]) and mode != '':
        return ''
    #if (mode not in FileTypeMapTable[ftype]['mode']) and mode != '':
    #    return ''
    return FileTypeMapTable[ftype]['pathfunc'](user,ftype,mode,filename) 

#history filepath
    '''
def FilePath_History(user,ftype,mode,filename)
    if ftype not in FileTypeMapTable:
        return ''
    path = resource_root + FileTypeMapTable[ftype]['path']
    if 'mode' in FileTypeMapTable[ftype]:
        if mode in FileTypeMapTable[ftype]['mode']:
            # 消息中的图片类型，会多建一级目录
            if mode == 'image':
                path += str(user) + "/" + mode + "/" + "original" + "/" + filename
            elif mode == 'default':
                path += mode + "/" + filename
            else:
                path += str(user) + "/" + mode + "/" + filename
            return path
        else:
            if ftype == 'backgroundpic':
                path += str(user) + "/" + filename
                return path
            return ''
    else:
        if mode != '':
            return ''
    if ftype == 'official':
        return path + filename
    path += str(user) + "/" + filename
    return path
    '''
####################################################

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

#############################################################
#####old api

class  up_voice_wt(tornado.web.RequestHandler):
    def post(self):
        username = self.request.headers.get('User-Name','')
        md5 = self.request.headers.get('MD5',0)
        filename = self.request.files['uploadedfile'][0]['filename']
        filecontent = self.request.files['uploadedfile'][0]['body']
        ftype = self.request.files['uploadedfile'][0]['content_type']
        if not checkfilecontentpattern(filename,ftype,filecontent):
            logging.info("checkfilecontentpattern fail:[%s,%s]" % (username,filename))
            self.finish()
            return
        if '' == username:
            # 用户名包含在文件名中
            username = filename[0:filename.find('_')]
        logging.info("up_voice_wt[%s,%s]" % (username,filename))
        if ftype.find('image') != -1:
           filepath = FilePath(username,'chat','image',filename)
           mode = 'image'
        else:
           filepath = FilePath(username,'chat','voice',filename)
           mode = 'voice'
        if not os.path.exists(os.path.dirname(filepath)):
            os.makedirs(os.path.dirname(filepath))
        f = open(filepath,'wb')
        f.write(filecontent)
        f.close()
        db = self.application.database
        MsgProcess(db,{'username':username,'filetype':'chat','mode':mode,'filename':filename})
        self.finish()

class down_voice_wt(tornado.web.RequestHandler):
    def get(self):
        imagename = self.get_argument('image_file','').encode('utf-8')
        voicename = self.get_argument('voice_file','').encode('utf-8')
        mode = self.get_argument('mode','small')

        if imagename != '':
            pos = imagename.find('_')
            if pos == -1:
               filepath = resource_root + '/prompt/' + imagename     
            else:
                username = imagename[:pos]
                filepath = FilePath(username,"chat",'image',imagename)
                if 'small' == mode:
                    filepath = filepath.replace('original','small')
        else:
            username = voicename[:voicename.find('_')]
            filepath = FilePath(username,"chat",'voice',voicename)

        if not os.path.exists(filepath):
            self.write('error')
            self.finish()
            return
        self.set_header ('Content-Type', 'application/octet-stream')
        self.set_header ('Content-Disposition', 'attachment; filename=%s' % (imagename if '' != imagename else voicename))
        self.set_header ('Content-Length',os.path.getsize(filepath))
        with open(filepath, 'rb') as f:
            data = f.read()
            self.write(data)
        self.finish()

downloadpool = ThreadPoolExecutor(max_workers=1000)
uploadpool = ThreadPoolExecutor(max_workers=1000)

@run_on_executor(executor='uploadexecutor')
def upload_common(self, type, mode):
    logging.info('thread-id:%s'%threading.current_thread())
    logging.info('thread-num:%s'%threading.activeCount())
    username = self.request.headers.get('User-Name','')
    self.set_header("Content-Type", "text/plain")
    if '' == username:
        self.write('upload err')
        return 'err'
    md5 = self.request.headers.get('MD5',0)
    filename = self.request.files['uploadedfile'][0]['filename']
    filecontent = self.request.files['uploadedfile'][0]['body']
    if not checkfilecontentpattern(filename,type,filecontent):
        logging.info('checkfilecontentpattern fail:%s,%s' % (username,filename))
        return 'err'
    if filecontent[-2:] == '\r\n':
    	filecontent = filecontent[0:-2]
    if not check_md5(filecontent, md5):
        if 'image' == type:
            self.write('MD5 Error')
            return 'err'
    filepath = FilePath(username,type,mode,filename)
    if not os.path.exists(os.path.dirname(filepath)):
        os.makedirs(os.path.dirname(filepath))
    f = open(filepath,'wb')
    f.write(filecontent)
    f.close()
    db = self.application.database
    if 'image' == type:
        ImageProcess(db,{'username':username,'filetype':'image','mode':'original','filename':filename})
    elif 'voice' == type:
        VoiceProcess(db,{'username':username,'filetype':'voice','':'original','filename':filename})
    elif 'video' == type:
        VideoProcess(db,{'username':username,'filetype':'video','':'original','filename':filename})
    self.write('upload ok')

class  Upload_image(tornado.web.RequestHandler):
    uploadexecutor = uploadpool
    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def post(self):
        logging.info("Upload_image post.............")
        yield upload_common(self, 'image', 'original')
        self.finish()
        
class Upload_voice(tornado.web.RequestHandler):
    uploadexecutor = uploadpool
    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def post(self):
        logging.info("Upload_voice post.............")
        yield upload_common(self, 'voice', '')
        self.finish()

class Upload_video(tornado.web.RequestHandler):
    uploadexecutor = uploadpool
    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def post(self):
        logging.info("Upload_video post.............")
        yield upload_common(self, 'video', '')
        self.finish()


@run_on_executor(executor='downloadexecutor')
def download_common(self, type):
    logging.info('thread-id:%s'%threading.current_thread())
    logging.info('thread-num:%s'%threading.activeCount())

    mode = self.get_argument('mode','').encode('utf-8')
    filename = self.get_argument('filename','').encode('utf-8')
    username = self.get_argument('username','')

    logging.info('type: %s ,mode: %s ,filename: %s ,username:%s' % (type, mode, filename, username))
   
    if 'image' == type and '' == mode:
        mode = 'small'
    if 'voice' == type and '' != mode:
        mode = ''
    filepath = FilePath(username,type,mode,filename)
    logging.info(filepath)
    if not os.path.exists(filepath):
        self.write('error')
        return
    self.set_header ('Content-Type', 'application/octet-stream')
    self.set_header ('Content-Disposition', 'attachment; filename=%s' % filename)
    self.set_header ('Content-Length',os.path.getsize(filepath))
    with open(filepath, 'rb') as f:
        data = f.read()
        self.write(data)


class Download_image(tornado.web.RequestHandler):
    downloadexecutor = downloadpool
    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        yield download_common(self, "image")
        self.finish()

class Download_voice(tornado.web.RequestHandler):
    downloadexecutor = downloadpool
    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        yield download_common(self, "voice")
        self.finish()

class Download_video(tornado.web.RequestHandler):
    downloadexecutor = downloadpool
    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        yield download_common(self, "video")
        self.finish()

class Download_video_snapshot(tornado.web.RequestHandler):
    downloadexecutor = downloadpool
    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        yield download_common(self, "snapshot")
        self.finish()

class Official_topics_pics(tornado.web.RequestHandler):
    downloadexecutor = downloadpool
    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        yield download_common(self, "official")
        self.finish()

unstandard_list = ["0963038773", "3332656140", "6475028210", \
                   "6981108038", "705277292", "886987023865"]

class User_Background_Picture(tornado.web.RequestHandler):
    def post(self):
        logging.info("User_Background_Picture post.............")
        md5 = self.request.headers.get('MD5',0)
        username = self.request.headers.get('User-Name','')
        filename = self.request.files['uploadedfile'][0]['filename'].encode('utf-8')
        if '' == username:
            # 用户名包含在文件名中，对于非手机号标准长度的其他格式的账号，会有问题.等新版APP普及后，从头部的UserID取得数据
            for sname in unstandard_list:
                if filename.startswith(sname):
                    username = filename[:len(sname)]
                    break
            else:
                username = filename[:11]
        '''
        在原来的旧接口中，服务器根据用户上传的背景图片的文件名进行uuid3运算，以运算值作为新的文件名在文件服务器上存储文件，
        但是服务器在数据库中记录用户信息时，依然存储的是原有的文件名
        '''
        filecontent = self.request.files['uploadedfile'][0]['body'] 
        filepath = FilePath(username,'backgroundpic','',filename)
        if not os.path.exists(os.path.dirname(filepath)):
            os.makedirs(os.path.dirname(filepath))
        f = open(filepath,'wb')
        f.write(filecontent)
        f.close()
        db = self.application.database
        BgPicProcess(db,{'username':username,'filetype':'backgroundpic','mode':'','filename':filename})
        self.write('upload ok')
        self.finish()

    def get(self):
        filename = self.get_argument('filename','').encode('utf-8')
        if filename.startswith('picture'):
            filepath = resource_root + '/' + 'backgroundpic' + '/' + 'default' + '/' + filename
        else:
            for sname in unstandard_list:
                if filename.startswith(sname):
                    username = filename[:len(sname)]
                    break
            else:
                username = filename[:11]
            logging.info(filename)
            filepath = FilePath(username,"backgroundpic",'',filename)
            logging.info(filepath)
            if not os.path.exists(filepath):
                self.write('get default backgroundpic error')
                self.finish()
                return
        self.set_header ('Content-Type', 'application/octet-stream')
        self.set_header ('Content-Disposition', 'attachment; filename=%s' % filename)
        self.set_header ('Content-Length',os.path.getsize(filepath))
        with open(filepath, 'rb') as f:
            data = f.read()
            self.write(data)
        self.finish()


class Upload_User_Avatar(tornado.web.RequestHandler):
    def post(self):
        logging.info("Upload_User_Avatar post.............")
        md5 = self.request.headers.get('MD5',0)
        username = self.request.headers.get('User-Name','')
        filename = self.request.files['uploadedfile'][0]['filename'].encode('utf-8')
        if '' == username:
            # 用户名包含在文件名中，对于非手机号标准长度的其他格式的账号，会有问题.等新版APP普及后，从头部的UserID取得数据
            for sname in unstandard_list:
                if filename.startswith(sname):
                    username = filename[:len(sname)]
                    break
            else:
                username = filename[:11]
        filecontent = self.request.files['uploadedfile'][0]['body'] 
        filepath = FilePath(username,'avatar','original',filename)
        if not os.path.exists(os.path.dirname(filepath)):
            os.makedirs(os.path.dirname(filepath))
        f = open(filepath,'wb')
        f.write(filecontent)
        f.close()
        db = self.application.database
        AvatarProcess(db,{'username':username,'filetype':'avatar','mode':'original','filename':filename})

class Download_User_Avatar(tornado.web.RequestHandler):
    def get(self):
        filename = self.get_argument('avatar','').encode('utf-8')
        if filename.startswith('icon_user'):
            filepath = resource_root + '/' + 'avatar' + '/' + 'default' + '/' + filename
        else:
            mode = self.get_argument('mode','small')
            for sname in unstandard_list:
                if filename.startswith(sname):
                    username = filename[:len(sname)]
                    break
            else:
                username = filename[:11]
            # 客户端请求用户头像图片的原图
            filepath = FilePath(username,"avatar",mode,filename)
            # 客户端请求用户图片的缩略图
            if 'small' == mode:
                filepath = filepath.replace('original','small')
            if not os.path.exists(filepath):
                self.write('error')
                self.finish()
                return
        self.set_header ('Content-Type', 'application/octet-stream')
        self.set_header ('Content-Disposition', 'attachment; filename=%s' % filename)
        self.set_header ('Content-Length',os.path.getsize(filepath))
        with open(filepath, 'rb') as f:
            data = f.read()
            self.write(data)
        self.finish()

###########################################################

class InnerHandler(tornado.web.RequestHandler):
    executor = ThreadPoolExecutor(20)
    ModuleMapTable = {
            'poster':{'path':'/poster'},
    }

    @run_on_executor
    def writefile(self,filepath,filecontent):
        path = os.path.dirname(filepath)
        if not os.path.exists(path):
            os.makedirs(path)
        with open(filepath,'wb') as f:
            f.write(filecontent)
    @run_on_executor    
    def readfile(self,filepath):
        if not os.path.exists(filepath):
           raise IOError('filepath is not exist')
        with open(filepath, 'rb') as f:
           data = f.read()
        return data

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        logging.info('InnerHandler get............')
        try:
            url = self.request.uri
            module = url.split('?')[0].split('/')[1]
            logging.info('module:%s'%module)
            filename = self.get_argument('filename','').encode('utf-8')
            if filename == '':
                raise Exception('filename is empty')
            filepath = resource_root + self.ModuleMapTable[module]['path'] + '/' + filename
            logging.info(filepath)
            data = yield self.readfile(filepath) 
            self.set_header ('Result','0')
            self.set_header ('Content-Type', 'application/octet-stream')
            self.set_header ('Content-Disposition', 'attachment; filename=%s' % filename)
            self.set_header ('Content-Length',os.path.getsize(filepath))
            self.write(data)
            self.finish()
        except Exception as e:
            logging.info(traceback.format_exc())
            self.set_header('Result','9999')
            self.finish()
            
    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def post(self):
        logging.info('InnerHandler post............')
        try:
            md5 = self.request.headers.get('MD5',0)
            filecontent = self.request.body
            url = self.request.uri
            module = url.split('?')[0].split('/')[1]
            logging.info('module:%s'%module)
            if len(filecontent) == 0:
                raise Exception('file is empty')
            if check_md5(filecontent,md5):
                filepath = resource_root + self.ModuleMapTable[module]['path'] + '/' + md5
                logging.info(filepath)
                yield self.writefile(filepath,filecontent)
                self.set_header('Result','0')
                self.set_header('Filename',md5)
                self.finish()
            else:
                raise Exception('check md5sum fail')
        except Exception as e:
            logging.info(traceback.format_exc())
            self.set_header('Result','9999')
            self.finish()
        
###########################################################
#####main.py
class Application(tornado.web.Application):
    def __init__(self,config):
        handlers=[
            (r"/resource", FileHandler),
            (r"/poster", InnerHandler),
            (r"/upload_voice_wt",up_voice_wt),
            (r"/download_voice_wt",down_voice_wt),
            (r"/download_voice_wt.jpg",down_voice_wt),
            (r"/share",Upload_image),
            (r"/share/upload",Upload_image),
            (r"/share/upload/image",Upload_image),
            (r"/share/upload/voice",Upload_voice),
            (r"/share/upload/video",Upload_video),
            (r"/share/download",Download_image),
            (r"/share/download.jpg",Download_image),
            (r"/share/download/image",Download_image),
            (r"/share/download/voice",Download_voice),
            (r"/share/download/video",Download_video),
            (r"/share/download/video.gif",Download_video),
            (r"/share/download/video_snapshot",Download_video_snapshot),
            (r"/share/download/video_snapshot.png",Download_video_snapshot),
            (r"/share/offical_topics_pics",Official_topics_pics),
            (r"/share/backgroundpic",User_Background_Picture),
            (r"/up_avatar.php",Upload_User_Avatar),
            (r"/down_avatar.php",Download_User_Avatar)]
        logging.info('Application init...........')
        self.database = DataBase(config)
        tornado.web.Application.__init__(self, handlers, debug=True)

if __name__ == '__main__':
    tornado.options.parse_command_line()
    tornado.options.parse_config_file(options.config,False)
    resource_root = options['resource_root']
    logging.info("File Root Path:%s"%resource_root)
    logging.info("Server Running in Port:%s"%options.port)
    logging.info(threading.current_thread())
    app = Application(options)
    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()

