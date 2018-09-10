#!/usr/bin/python
# -*- coding: utf-8 -*-

import queue
import threading
import pymongo
import os.path
import hashlib

from pymongo import MongoClient
from html.parser import HTMLParser
from importlib import reload


NR_OF_THREADS   = 10
BYTECODE        = True
MONGO_HOST      = '127.0.0.1'
MONGO_PORT      = 27017
DATABASE        = 'ethereum'
COLLECTION      = 'contracts'
CONTRACT_FOLDER = "../contracts/"


exitFlag = 0

class searchThread(threading.Thread):
   def __init__(self, threadID, queue, collection, parser):
      threading.Thread.__init__(self)
      self.threadID = threadID
      self.queue = queue
      self.collection = collection
      self.parser = parser
   def run(self):
      searchContract(self.queue, self.collection, self.parser)

def searchContract(queue, collection, parser):
    while not exitFlag:
        queueLock.acquire()
        if not queue.empty():
            #address = queue.get()
            #queueLock.release()
            #result = collection.find({"address": address})

            contract = queue.get()
            queueLock.release()

            #byteCode = queue.get()
            #queueLock.release()
            #result = collection.find({"byteCode": byteCode}).sort("balance", pymongo.DESCENDING).limit(1)
            #if result.count() > 0:
            #    contract = list(result)[0]
            #print('Writing contract to file: '+contract['address'])
            file_path = CONTRACT_FOLDER+str(contract['address'])
            #file_path = CONTRACT_FOLDER+str(contract['contractName'])
            extension = ""
            counter = 1
            # Write byte code to file
            if BYTECODE:
                writeLock.acquire()
                while os.path.exists(file_path+extension+".bin"):
                    counter += 1
                    extension = "_"+str(counter)
                file = open(file_path+extension+".bin", "w")
                file.write(parser.unescape(contract['byteCode']))
                file.close()
                writeLock.release()
            # Write source code to file
            else:
                writeLock.acquire()
                while os.path.exists(file_path+extension+".sol"):
                    counter += 1
                    extension = "_"+str(counter)
                file = open(file_path+extension+".sol", "w")
                file.write(parser.unescape(contract['sourceCode']))
                file.close()
                writeLock.release()
        else:
            queueLock.release()

if __name__ == "__main__":

    #reload(sys)
    #sys.setdefaultencoding("utf-8")

    queueLock = threading.Lock()
    q = queue.Queue()

    writeLock = threading.Lock()

    # Create new threads
    threads = []
    threadID = 1
    for i in range(NR_OF_THREADS):
        collection = MongoClient(MONGO_HOST, MONGO_PORT)[DATABASE][COLLECTION]
        parser = HTMLParser()
        thread = searchThread(threadID, q, collection, parser)
        thread.start()
        threads.append(thread)
        threadID += 1

    collection = MongoClient(MONGO_HOST, MONGO_PORT)[DATABASE][COLLECTION]
    cursor = collection.find()
    print("Total number of smart contracts: "+str(cursor.count()))

    #cursor = collection.find({"balance": {"$gt": 0}})
    #print("Total number of smart contracts with a balance above zero: "+str(cursor.count()))
    uniques = set()
    contracts = []
    #m = hashlib.sha256()
    for contract in cursor:
        #m.update(contract["byteCode"].encode('utf-8'))
        #hash = m.hexdigest()
        #unique.add(hash)
        if not contract["byteCode"].encode('utf-8') in uniques:
            uniques.add(contract["byteCode"].encode('utf-8'))
            contracts.append(contract)

    #contracts = cursor.distinct("byteCode")
    print("Total number of smart contracts that are distinct: "+str(len(uniques)))
    print(len(contracts))
    #print((float(len(unique)) / float(cursor.count())) * 100.0)
    #print(100-(float(len(unique)) / float(cursor.count())) * 100.0)
    #print("Total number of smart contracts with a balance above zero and that are distinct: "+str(len(contracts)))


    # Fill the queue with contracts
    queueLock.acquire()
    #for contract in cursor:
    #    q.put(contract["address"])

    for i in range(len(contracts)):
        #if contracts[i] != "":
        q.put(contracts[i])
    queueLock.release()

    print("Queue contains "+str(q.qsize())+" contracts...")

    # Wait for queue to empty
    while not q.empty():
        pass

    # Notify threads it's time to exit
    exitFlag = 1

    # Wait for all threads to complete
    for t in threads:
       t.join()

    print('\nDone')
