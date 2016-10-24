#!/usr/bin/python
#-*- encoding:utf-8 -*-
from database import *
from utils import *

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
        return True
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


        
        


