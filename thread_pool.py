#!/usr/bin/python
#coding=utf-8


import MySQLdb
import sys
import threading
import time
import datetime
import Queue
import copy
import random
import md5
import base64
import types

class ThreadWork(object):
	def __init__(self,func,*args):
		self.func = func
		self.argvs = []
		print "$$$$$$$$$$$$$$",self.func.__name__,args
		if args != ():
			for value in args:
				var = copy.deepcopy(value)
				self.argvs.append(var)
		#else:
			#self.argvs = None
		print "*************",self.argvs
		
class ThreadPool(object):

	def __init__(self,Tnum,Qnum=0,func=None):
		self.threadnum = int(Tnum)
		self.queuenum = int(Qnum)
		self.threads = []
		self.threadcon = threading.Condition()
		self.workqueue =  Queue.Queue(Qnum)
		if func:
			print "ThreadPool process function is %s" % str(func)
			self.func = func
			for i in range(self.threadnum):
				tn = "Thread-"+str(i)+" : "+func.__name__ + " starting"
				tnx = "Thread-"+str(i)
				thd = threading.Thread(target=func,args=(),name=tnx)
				self.threads.append(thd)
		else:
			print "ThreadPool process function is default"
			self.func = self.__ThreadWorkFunc
			self.CreateThread(self.func,self.threadnum)

	def CreateThread(self,func,num):
		x = int(num)	
		for i in range(x):
			thd = threading.Thread(target=func,args=(str(i)),name=str(i))
			self.threads.append(thd)
		print "ThreadPool create %d threads"  % x
		return self.threads


	def __ThreadWorkFunc(self,name):
		while True:
			self.threadcon.acquire()	
			while self.workqueue.empty():
				print "Thread[%s] is waiting...." % name
				self.threadcon.wait()
						
			threadwork = self.workqueue.get();	
			if isinstance(threadwork,ThreadWork):
				strargs = ""
				funcname = threadwork.func.__name__
				for x in threadwork.argvs:	
					strargs = strargs + repr(x)
					strargs = strargs + ","
					'''
					if type(x) is types.StringType:
						strargs = strargs + "'" + repr(x) + "'"
						strargs = strargs + ","
					else:	
						strargs = strargs + str(x)
						strargs = strargs + ","
					'''
				funexc = funcname + "(" + strargs[:-1] + ")"
				print funexc
				eval(funexc)
				print "work is be processed OK!"
			else:
				print "The type of work cannot be processed!"
			self.threadcon.notify()
			self.threadcon.release()

	def AddWork(self,threadwork):
		if isinstance(threadwork,ThreadWork):
			self.threadcon.acquire()
			while self.workqueue.full():
				self.threadcon.wait()
			self.workqueue.put(threadwork);
			self.threadcon.notify()
			self.threadcon.release()
		else:
			print "threadpool add job fail,make sure the type of job is ThreadWork!"

	def Start(self):
		for sw in self.threads:
			print sw.getName(),"start......."
			sw.start()	

		
mysqlconf = {"host":"localhost","user":"root","passwd":"root","db":"yugongtest","port":3306}
insertsql = "insert into yugongtest.userinfo(phone,name,password,email,age,createtime,lastlogin_id) values('%s','%s','%s','%s',%d,'%s','%s');"	
def insertmysql():
	try:
		conn = MySQLdb.connect(host=mysqlconf["host"],user=mysqlconf["user"],\
		passwd=mysqlconf["passwd"],db=mysqlconf["db"],port=mysqlconf["port"])
		cur = conn.cursor()

		phone = random.choice(['139','188','185','136','158','151']) + "".join(random.choice("0123456789") for i in range(8))
		name = threading.currentThread().getName()
		email = "".join(random.choice('abcedfghijklmnopqrstuvwxyz') for i in range(5)) + "@" + random.choice(['126.com','163.com','qq.com','google.com'])
		age = random.randint(1,100)
		tm = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
		hsd = md5.new()
		passwd = str(hsd.hexdigest())
		loginid = base64.encodestring("".join(random.choice('abcedfghijklmnopqrstuvwxyz') for i in range(5)))

		excsql = insertsql % (phone,name,passwd,email,age,tm,loginid)

		print threading.currentThread().getName(),excsql

		cur.execute(excsql)	
		conn.commit()
		cur.close()
		conn.close()

	except MySQLdb.Error,e:
		print "MySQL Error %d:%s" % (e.args[0],e.args[1])


def whileinsert():
	while 1:
		insertmysql()



deletesql = "delete from yugongtest.userinfo;"
def deletemysql():
	try:
		conn = MySQLdb.connect(host=mysqlconf["host"],user=mysqlconf["user"],\
		passwd=mysqlconf["passwd"],db=mysqlconf["db"],port=mysqlconf["port"])
		cur = conn.cursor()
		excsql = deletesql 
		print '\n',excsql
		cur.execute(excsql)	
		conn.commit()
		cur.close()
		conn.close()
	except MySQLdb.Error,e:
		print "MySQL Error %d:%s" %(e.args[0],e.args[1])
		
	
def test():
	print "helloworld!!!!"
def test1(a,b):
	print "helloword",a,b
def test2(a,b,c):
	print "helloword",a,b,c
def test3(a,b,c):
	for i in a:
		print i
	for j in b:
		print j
	print c

if __name__ == "__main__":
	if len(sys.argv) < 2 or sys.argv[1] <= 0:
		print "usage: threadpool.py xxx!"	
		sys.exit()

	thread_num = sys.argv[1]
	print "create %s threading..........................!" % thread_num
#1
	#threadpool = ThreadPool(thread_num,func=whileinsert);
	#threadpool.Start()
	#deletemysql()
#2
	tp = ThreadPool(thread_num)
	job1 = ThreadWork(test1,"xxxxx","oooooo")
	#job2 = ThreadWork(test1,["122",19],["heho","world"])
	#job3 = ThreadWork(test2,[1,2,3,4,5,6,7,8,9],["heho","world"],"try it agin")
	#job4 = ThreadWork(test3,["122",19],{1:"dada",2:"222",3:"adfa"},"afdafasdfasf")
	tp.AddWork(job1)
	#tp.AddWork(job2)
	#tp.AddWork(job3)
	#tp.AddWork(job4)
	tp.Start()
