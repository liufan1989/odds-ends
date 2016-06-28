#!/bin/bash

table=$1
file=$2

if [ -z $1 ] || [ -z $2];then
echo "usage: ./sql_search.sh tablename file"
exit
fi

echo "You search table:[$1],In File:[$2]"
echo "++++++++++++++++++++++++++++++"
grep "$1" -C 5 -w "$2" | sed 's/^[ \t]*//g' > "tmp.log"
echo "Generate tmp.log"
i=0
while read line
do
    flag=`echo $line|grep $1|wc -l`
    echo 
    if [ $flag = 0 ]
    then
        echo "$i  no,match!"
    else
        echo "$i yes,match!"
        newline=$line 
        m1=`echo $newline | grep "insert"|wc -l `
        m2=`echo $newline | grep "INSERT"|wc -l `
        m3=`echo $newline | grep "update"|wc -l `
        m4=`echo $newline | grep "UPDATE"|wc -l `
        m5=`echo $newline | grep "select"|wc -l `
        m6=`echo $newline | grep "SELECT"|wc -l `
        if [ "$m1" = 1 -o "$m2" = 1 -o "$m3" = 1 -o "$m4" = 1 -o "$m5" = 1 -o "$m6" = 1 ]
        then
            while :
            do
                postfix=${newline%\%*}
                echo ${newline:${#newline}-1:1}
                if [ "${newline:${#newline}-1:1}" = '\' ]
                then
                   echo '===='
                   set -f 
                   echo -n $postfix >> "$table.txt"
                   set +f
                   read line
                   newline=$line
                else  
                   set -f
                   echo  $postfix >> "$table.txt"
                   set +f
                   read line
                   break
                fi
            done
        fi

    fi
i=`expr $i + 1`
done < "tmp.log"
rm -f "tmp.log"
#if [ ! -d ${dst} ];then
#	mkdir -p ${dst}
#	echo "mkdir ${dst} ok!"
#else
#	cd ${dst}
#	rm -rf * 
#	echo "clean ${dst} ok!"
#fi
#
#echo "copy ${src} to ${dst}...."
