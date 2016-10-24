#!/usr/bin/python
#-*- encoding:utf-8 -*-

import logging
import shutil
import os
import PIL.Image as Image
import pdb
import traceback
import hashlib
import subprocess as sp
import re
import magic
from itertools import product

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

def get_video_lite_info(full_path):
    """
    获取视频相关信息
    :param full_path: 视频文件绝对路径
    :return:  视频宽度, 视频高度, 视频时长
    """
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
    return  width, height, duration, rotate

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

def VideoFirstFrame(srcfile,dstpath,rotate=0):
    sp.call(['ffmpeg', '-i', srcfile, '-ss', '0', '-vframes', '100', '-f', 'image2', '-y', dstpath],close_fds=True)
    '''
    if rotate == 0:
        sp.call(['ffmpeg', '-i', srcfile, '-ss', '0', '-vframes', '100', '-f', 'image2', '-y', dstpath],close_fds=True)
    elif rotate == 90:
        sp.call(['ffmpeg', '-i', srcfile, '-ss', '0', '-vf', 'transpose=1', '-vframes', '100', '-f', 'image2', '-y', dstpath],close_fds=True)
    else:
        pass
    '''


def check_md5(filecontent,md5code):
    filehash = hashlib.md5()
    filehash.update(filecontent)
    hexdig = filehash.hexdigest()
    logging.info("client_md5:%s,server_md5:%s" % (md5code,hexdig))
    if hexdig == md5code:
        return True
    else:
        return False 

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


def checkfiletype(filename,ftype):
    res = magic.from_file(filename, mime=True)
    return res.startswith(ftype)
        


hexstring = '0123456789abcdef'
def md5_file_path(path,level,prefixnum):
    pathlist = []
    if not path.endswith('/'):
        path += '/'
    hexlist = [] 
    i = 0 
    while i < prefixnum:
        hexlist.append(hexstring)
        i += 1

    for x in product(*hexlist):
        temppath = ""
        temppath += path + "".join(x)
        if not os.path.exists(temppath):                                                                                                                            
           os.makedirs(temppath)
        logging.info("mkdir:%s",temppath)
        pathlist.append(temppath)
    if level == 1:
        return
    else:
        for x in pathlist:
            md5_file_path(x,level-1,prefixnum);
        return

