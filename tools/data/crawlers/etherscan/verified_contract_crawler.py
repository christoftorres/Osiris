#!/usr/bin/python
# -*- coding: utf-8 -*-

import Queue
import threading
import pymongo
import datetime
import cfscrape
import re
import time

from web3 import Web3, KeepAliveRPCProvider
from bson.decimal128 import Decimal128
from pymongo import MongoClient

web3 = Web3(KeepAliveRPCProvider(host='127.0.0.1', port='8545'))
latestBlock = web3.eth.getBlock('latest')
exitFlag = 0

retries = 10
timeout = 1 # seconds

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
      searchContract(self.queue, self.collection, self.scraper)

def searchContract(queue, collection, scraper):
    while not exitFlag:
        queueLock.acquire()
        if not queue.empty():
            contract = queue.get()
            queueLock.release()
            print('Searching contract '+str(contract['address'])+'...')
            result = collection.find({'address': contract['address']})
            if result.count() == 0:
                success = False
                webpage = ""
                tries = 0
                while (not success and tries <= retries):
                    try:
                        time.sleep(2)
                        webpage = scraper.get('https://etherscan.io/address/'+str(contract['address'])).content
                        contract['contractName'] = re.compile("<td>Contract Name:</td><td>(.+?)</td>").findall(webpage.replace('\n','').replace('\t',''))[0].replace(' ', '')
                        print contract['contractName']
                        contract['balance'] = web3.fromWei(web3.eth.getBalance(contract['address']), 'ether')
                        if not contract['balance'] == 0:
                            contract['balance'] = Decimal128(contract['balance'])
                        else:
                            contract['balance'] = Decimal128('0')
                        print contract['balance']
                        contract['nrOfTransactions'] = int(re.compile("<span title='Normal Transactions' rel='tooltip' data-placement='bottom'>(.+?) txn.*?</span>").findall(webpage)[0])
                        print contract['nrOfTransactions']
                        contract['compilerVersion'] = re.compile("<td>Compiler Version:</td><td>(.+?)</td>").findall(webpage.replace('\n','').replace('\t',''))[0]
                        print contract['compilerVersion']
                        contract['optimizationEnabled'] = bool(re.compile("<td>Optimization Enabled:[\n.]<\/td>.*?[\n.].*?<td>[.\n]([\s\S]+?)[\n.]<\/td>", re.MULTILINE).findall(webpage)[0])
                        print contract['optimizationEnabled']
                        contract['optimizerRuns'] = int(re.compile("<td>Runs.*?[\n.]<\/td>.*?[\n.].*?<td>[.\n]([\s\S]+?)[\n.]<\/td>", re.MULTILINE).findall(webpage)[0])
                        print contract['optimizerRuns']
                        contract['sourceCode'] = re.compile("<pre class='js-sourcecopyarea' id='editor' style='.+?'>([\s\S]+?)</pre>", re.MULTILINE).findall(webpage)[0]
                        contract['abi'] = re.compile("<pre class='wordwrap js-copytextarea2' id='js-copytextarea2' style='.+?'>([\s\S]+?)</pre>", re.MULTILINE).findall(webpage)[0]
                        contract['byteCode'] = web3.eth.getCode(contract['address']).replace("0x", "")
                        collection.insert_one(contract)
                        # Indexing...
                        if 'address' not in collection.index_information():
                            collection.create_index('address', unique=True)
                            collection.create_index('dateVerified')
                            collection.create_index('contractName')
                            collection.create_index('balance')
                            collection.create_index('nrOfTransactions')
                            collection.create_index('compilerVersion')
                            collection.create_index('optimizationEnabled')
                            collection.create_index('optimizerRuns')
                        success = True
                    except Exception as e:
                        if "Request Throttled" in webpage:
                            print("Request throttled contract address "+contract['address'])
                        else:
                            print("Unexpected error at contract address "+contract['address']+": "+str(e))
                        tries += 1
                        if (tries < retries):
                            print("Retrying in "+str(int(timeout))+" sec... ("+str(tries)+" of "+str(retries)+" retries)")
                            time.sleep(tries * timeout)
                        else:
                            print('Error: contract '+contract['address']+' could not be added.')
                        pass
                    if (success):
                        print('Contract '+contract['address']+' has been successfully added.')
            else:
                print('Contract '+contract['address']+' already exists...')
        else:
            queueLock.release()

if __name__ == "__main__":
    init()

    queueLock = threading.Lock()
    queue = Queue.Queue()

    # Create new threads
    threads = []
    threadID = 1
    for i in range(5):
        collection = MongoClient('127.0.0.1', 27017)['ethereum']['verified_contracts']
        scraper = cfscrape.CloudflareScraper()
        thread = searchThread(threadID, queue, collection, scraper)
        thread.start()
        threads.append(thread)
        threadID += 1

    # Fill the queue with contract objects
    scraper = cfscrape.CloudflareScraper()
    content = scraper.get('https://etherscan.io/contractsVerified').content
    lastPage = int(re.compile("Page <b>1</b> of <b>(.+?)</b>").findall(content)[0])
    queueLock.acquire()
    for i in range(lastPage, 0, -1):
    #for i in range(1, lastPage+1):
        time.sleep(timeout)
        content = scraper.get('https://etherscan.io/contractsVerified/'+str(i)).content
        result = re.compile("<a href='/address/.*?' class='address-tag'>(.+?)</a>.*?</td><td>.*?</td><td>.*?</td><td>.*? Ether</td><td>.*?</td><td>(.*?)</td>").findall(content)
        for address, dateVerified in result:
            contract = {}
            contract['address'] = address.lower()
            contract['dateVerified'] = dateVerified
            queue.put(contract)
    queueLock.release()

    print('Searching for '+str(queue.qsize())+' verified contracts...\n')

    # Wait for queue to empty
    while not queue.empty():
        pass

    # Notify threads it's time to exit
    exitFlag = 1

    # Wait for all threads to complete
    for t in threads:
       t.join()

    print('\nDone')
