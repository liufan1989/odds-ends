#!/usr/bin/python
#-*- encoding:utf-8 -*-
from utils import *
from constants import *
from fdfs_client.client import *
from tornado.concurrent import run_on_executor

def videosnapshot(srcpath):
    srcdir = srcpath[0:srcpath.rfind('/')]
    dstpath = srcdir.replace("video","snapshot")
    if not os.path.exists(dstpath):
        os.makedirs(dstpath)
    dstfile = os.path.basename(srcpath).split(".")[0]
    dstpath = dstpath + '/' + dstfile
    VideoFirstFrame(srcpath,dstpath)    

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

fdfs_client = Fdfs_client('./fdfs_python_client.conf')

@run_on_executor
def fastfdfs_postprocess(self,database,fileinfo):
    grouplist = []

    for x in fileinfo:

        if x['ftype'].startswith('video'):
            logging.info('fastfdfs:video:%s',x['filepath'])
            
            width, height, duration,rotate = get_video_lite_info(x['filepath'])
            logging.info("rotate:%s",rotate)

            videosnapfile = x['filepath']+"-vs" 
            VideoFirstFrame(x['filepath'],videosnapfile,rotate)    

            os.rename(x['filepath'],x['filepath'] + '.mp4')
            x['filepath'] = x['filepath'] + '.mp4'

            fdfs_client = Fdfs_client('./fdfs_python_client.conf')
            ret = fdfs_client.upload_by_filename(x['filepath'],{'ext':'mp4','size':x['fsize'],'md5':x['fmd5'],'width':width,'height':height,'duration':duration})

            logging.info(ret)
            if ret['Status'] != 'Upload successed.':
                raise Exception('fastdfs video upload fail')

            exret = fdfs_client.upload_slave_by_filename(videosnapfile,ret['Remote file_id'],".jpg")

            logging.info(exret)
            if exret['Status'] != 'Upload slave file successed.':
                raise Exception('fastdfs video snapshot upload fail')

            grouplist.append([x['filename'],ret['Remote file_id']])

        elif x['ftype'].startswith('image'):
            logging.info('fastfdfs:image:%s',x['filepath'])
        else:
            logging.info('fastfdfs post process ftype error')
            raise Exception('fastdfs ftype error')

    return grouplist
    

#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
def ImagePath(user,ftype,mode,filename):
    return GlobalVar.resource_root + GlobalVar.topic_root + '/' + user + '/' + mode + '/' + filename
def VideoPath(user,ftype,mode,filename):
    return GlobalVar.resource_root + GlobalVar.topic_root + '/' + user + '/' + 'video' + '/' + filename
def SnapshotPath(user,ftype,mode,filename):
    return GlobalVar.resource_root + GlobalVar.topic_root + '/' + user + '/' + 'snapshot' + '/' + filename
def VoicePath(user,ftype,mode,filename):
    return GlobalVar.resource_root + GlobalVar.topic_root + '/' + user + '/' + 'voice' + '/' + filename
def ChatPath(user,ftype,mode,filename):
    chatbasepath = GlobalVar.resource_root + '/'  + 'chat' + '/' + user + '/' + mode + '/'
    if mode == 'image':
        return chatbasepath + 'original' + '/' +  filename
    else:
        return chatbasepath + filename
def AvatarPath(user,ftype,mode,filename):
    avatarbasepath = GlobalVar.resource_root + '/' + 'avatar' + '/' 
    if mode == 'default':
        return avatarbasepath + 'default'  + '/' + filename
    else:
        return avatarbasepath + user +  '/' + mode + '/' + filename
def BgPicPath(user,ftype,mode,filename):
    bgpicbasepath = GlobalVar.resource_root + '/' + 'backgroundpic' + '/' 
    if mode == 'default':
        return bgpicbasepath + 'default'  + '/' + filename
    else:
        return bgpicbasepath + user + '/' + filename    
def OfficialPath(user,ftype,mode,filename):
    return GlobalVar.resource_root + '/' + 'official' + '/' + filename
def NewsPath(user,ftype,mode,filename):
    return GlobalVar.resource_root + '/' + 'news' + '/' + mode + '/' + filename
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
    path = GlobalVar.resource_root + FileTypeMapTable[ftype]['path']
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
