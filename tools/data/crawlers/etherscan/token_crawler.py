#!/usr/bin/python
# -*- coding: utf-8 -*-

import queue
import threading
import pymongo
import datetime
import cfscrape
import re
import time

from web3 import Web3, HTTPProvider
from bson.decimal128 import Decimal128
from pymongo import MongoClient

web3 = Web3(HTTPProvider('http://127.0.0.1:8545'))
latestBlock = web3.eth.getBlock('latest')
exitFlag = 0

retries = 10
timeout = 1 # seconds
wait    = 2 # seconds

def init():
    if web3.eth.syncing == False:
        print('Ethereum blockchain is up-to-date.')
        print('Latest block: '+str(latestBlock.number)+' ('+datetime.datetime.fromtimestamp(int(latestBlock.timestamp)).strftime('%d-%m-%Y %H:%M:%S')+')\n')
    else:
        print('Ethereum blockchain is currently syncing...')
        print('Latest block: '+str(latestBlock.number)+' ('+datetime.datetime.fromtimestamp(int(latestBlock.timestamp)).strftime('%d-%m-%Y %H:%M:%S')+')\n')

class searchThread(threading.Thread):
   def __init__(self, threadID, queue, collection, scraper):
      threading.Thread.__init__(self)
      self.threadID = threadID
      self.queue = queue
      self.collection = collection
      self.scraper = scraper
   def run(self):
      searchToken(self.queue, self.collection, self.scraper)

def searchToken(queue, collection, scraper):
    while not exitFlag:
        queueLock.acquire()
        if not queue.empty():
            token = queue.get()
            queueLock.release()
            print('Searching token '+str(token['address'])+'...')
            result = collection.find({'address': token['address']})
            if result.count() == 0:
                success = False
                webpage = ""
                tries = 0
                while (not success and tries <= retries):
                    try:
                        time.sleep(wait)
                        webpage = scraper.get('https://etherscan.io/address/'+str(token['address'])).content.decode('utf-8')
                        token['contractName'] = re.compile('<td>Contract<span class="hidden-su-xs"> Name</span>:</td><td>(.+?)</td>').findall(webpage.replace('\n','').replace('\t',''))[0].replace(' ', '')
                        #print("Contract Name: "+str(token['contractName']))

                        token['balance'] = web3.fromWei(web3.eth.getBalance(web3.toChecksumAddress(token['address'])), 'ether')
                        if not token['balance'] == 0:
                            token['balance'] = Decimal128(token['balance'])
                        else:
                            token['balance'] = Decimal128('0')
                        #print(token['balance'])

                        token['nrOfTransactions'] = int(re.compile("<span title='Normal Transactions' rel='tooltip' data-placement='bottom'>(.+?) txn.*?</span>").findall(webpage)[0])
                        #print("Nr Of Transactions: "+str(token['nrOfTransactions']))

                        token['compilerVersion'] = re.compile('<td>Compiler<span class="hidden-su-xs"> Version</span>:</td><td>(.+?)</td>').findall(webpage.replace('\n','').replace('\t',''))[0]
                        #print("Compiler Version: "+str(token['compilerVersion']))

                        token['optimizationEnabled'] = bool(re.compile('<td>Optimization<span class="hidden-su-xs"> Enabled</span>:[\n.]<\/td>.*?[\n.].*?<td>[.\n]([\s\S]+?)[\n.]<\/td>', re.MULTILINE).findall(webpage)[0])
                        #print("Optimization Enabled: "+str(token['optimizationEnabled']))

                        token['optimizerRuns'] = int(re.compile("<td>Runs.*?[\n.]<\/td>.*?[\n.].*?<td>[.\n]([\s\S]+?)[\n.]<\/td>", re.MULTILINE).findall(webpage)[0])
                        #print("Optimizer Runs: "+str(token['optimizerRuns']))

                        token['sourceCode'] = re.compile("<pre class='js-sourcecopyarea' id='editor' style='.+?'>([\s\S]+?)</pre>", re.MULTILINE).findall(webpage)[0]
                        #print("Source Code: "+str(token['sourceCode']))

                        token['abi'] = re.compile("<pre class='wordwrap js-copytextarea2' id='js-copytextarea2' style='.+?'>([\s\S]+?)</pre>", re.MULTILINE).findall(webpage)[0]
                        #print("ABI: "+str(token['abi']))

                        token['byteCode'] = web3.eth.getCode(web3.toChecksumAddress(token['address'])).hex().replace("0x", "")
                        #print("Byte Code: "+str(token['byteCode']))

                        collection.insert_one(token)
                        # Indexing...
                        if 'address' not in collection.index_information():
                            collection.create_index('address', unique=True)
                            collection.create_index('name')
                            collection.create_index('symbol')
                            collection.create_index('contractName')
                            collection.create_index('nrOfTransactions')
                            collection.create_index('compilerVersion')
                            collection.create_index('optimizationEnabled')
                            collection.create_index('optimizerRuns')
                        success = True
                    except Exception as e:
                        if "Request Throttled" in webpage:
                            print("Request throttled contract address "+token['address'])
                        else:
                            print("Unexpected error at contract address "+token['address']+": "+str(e))
                        tries += 1
                        if (tries < retries):
                            print("Retrying in "+str(int(timeout))+" sec... ("+str(tries)+" of "+str(retries)+" retries)")
                            time.sleep(tries * timeout)
                        else:
                            print('Error: token '+token['address']+' could not be added.')
                        pass
                    if (success):
                        print('Token '+token['address']+' has been successfully added.')
            else:
                print('Token '+token['address']+' already exists...')
        else:
            queueLock.release()

if __name__ == "__main__":
    init()

    queueLock = threading.Lock()
    q = queue.Queue()

    # Create new threads
    threads = []
    threadID = 1
    for i in range(5): # number of threads
        collection = MongoClient('127.0.0.1', 27017)['ethereum']['tokens']
        scraper = cfscrape.CloudflareScraper()
        thread = searchThread(threadID, q, collection, scraper)
        thread.start()
        threads.append(thread)
        threadID += 1

    # Fill the queue with tokens
    scraper = cfscrape.CloudflareScraper()
    content = scraper.get('https://etherscan.io/tokens').content.decode('utf-8')
    lastPage = int(re.compile("Page <b>1</b> of <b>(.+?)</b>").findall(content)[0])
    queueLock.acquire()
    #for i in range(lastPage, 0, -1):
    for i in range(1, lastPage+1):
        time.sleep(wait)
        content = scraper.get('https://etherscan.io/tokens?p='+str(i)).content.decode('utf-8')
        result = re.compile("<h5 style='margin-bottom:4px'><a href='/token/(.+?)'>(.+?) \((.+?)\)</a></h5>").findall(content)
        for address, name, symbol in result:
            token = {}
            token['address'] = address.lower()
            token['name']    = name
            token['symbol']  = symbol
            print(token)
            q.put(token)
    queueLock.release()

    print('Searching for '+str(q.qsize())+' tokens...\n')

    # Wait for queue to empty
    while not q.empty():
        pass

    # Notify threads it's time to exit
    exitFlag = 1

    # Wait for all threads to complete
    for t in threads:
       t.join()

    print('\nDone')
