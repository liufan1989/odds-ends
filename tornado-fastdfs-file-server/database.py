#!/usr/bin/python
#-*- encoding:utf-8 -*-

from DBUtils.PooledDB import PooledDB
from MySQLdb.cursors import DictCursor
import MySQLdb
import redis
import logging

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


