#!/usr/bin/python
#-*- encoding:utf-8 -*-

class GlobalVar:
    _resource_root = "/srv/liufan/resource"
    _topic_root = "/topic/"

    @property
    def resource_root(self):
        return _resource_root 

    @resource_root.setter
    def resource_root(self,x):
        _resource_root = x 

    @property
    def topic_root(self):
        return _topic_root 

    @topic_root.setter
    def topic_root(self,x):
        _topic_root = x 


