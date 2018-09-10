#!/usr/bin/python
# -*- coding: utf-8 -*-

import queue
import threading
import pymongo
import datetime
import cfscrape
import re
import time
import csv
import json
import traceback

from web3 import Web3, HTTPProvider
from bson.decimal128 import Decimal128
from pymongo import MongoClient

web3 = Web3(HTTPProvider('http://127.0.0.1:8545'))
latestBlock = web3.eth.getBlock('latest')
exitFlag = 0

retries = 5
timeout = 1 # seconds
wait    = 2 # seconds

#ETHERSCAN_URL = 'https://etherscan.io/address/'
ETHERSCAN_URL = 'https://ropsten.etherscan.io/address/'

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
            try:
                response = json.loads(scraper.get("https://etherscan.io/searchHandler?term="+str(contract['address'])).content.decode('utf-8'))
                if len(response) > 0:
                    contract['address'] = response[0].split("\t")[0]
            except:
                pass
            print('Searching contract '+str(contract['address'])+'...')
            result = collection.find({'address': contract['address']})
            if result.count() == 0:
                success = False
                webpage = ""
                tries = 0
                while (not success and tries <= retries):
                    try:
                        time.sleep(wait)
                        webpage = scraper.get(ETHERSCAN_URL+str(contract['address'])).content.decode('utf-8')
                        #if '<td>Contract<span class="hidden-su-xs"> Name</span>:</td>' in webpage:
                        contract['contractName'] = re.compile('<td>Contract<span class="hidden-su-xs"> Name</span>:</td><td>(.+?)</td>').findall(webpage.replace('\n','').replace('\t',''))[0].replace(' ', '')
                        #    print("Contract Name: "+str(contract['contractName']))

                        #if '<td>Compiler<span class="hidden-su-xs"> Version</span>:</td>' in webpage:
                        contract['compilerVersion'] = re.compile('<td>Compiler<span class="hidden-su-xs"> Version</span>:</td><td>(.+?)</td>').findall(webpage.replace('\n','').replace('\t',''))[0]
                            #print("Compiler Version: "+str(token['compilerVersion']))

                        #if '<td>Optimization<span class="hidden-su-xs"> Enabled</span>' in webpage:
                        contract['optimizationEnabled'] = bool(re.compile('<td>Optimization<span class="hidden-su-xs"> Enabled</span>:[\n.]<\/td>.*?[\n.].*?<td>[.\n]([\s\S]+?)[\n.]<\/td>', re.MULTILINE).findall(webpage)[0])
                            #print("Optimization Enabled: "+str(token['optimizationEnabled']))

                        #if "<td>Runs" in webpage:
                        runs = re.compile("<td>Runs.*?[\n.]<\/td>.*?[\n.].*?<td>[.\n]([\s\S]+?)[\n.]<\/td>", re.MULTILINE).findall(webpage)[0]
                        if not runs == "-NA-":
                            contract['optimizerRuns'] = int(runs)
                        else:
                            contract['optimizerRuns'] = 0
                                #print("Optimizer Runs: "+str(token['optimizerRuns']))

                        #if "pre class='js-sourcecopyarea' id='editor'" in webpage:
                        contract['sourceCode'] = re.compile("<pre class='js-sourcecopyarea' id='editor' style='.+?'>([\s\S]+?)</pre>", re.MULTILINE).findall(webpage)[0]
                            #print("Source Code: "+str(token['sourceCode']))

                        contract['balance'] = web3.fromWei(web3.eth.getBalance(web3.toChecksumAddress(contract['address'])), 'ether')
                        if not contract['balance'] == 0:
                            contract['balance'] = Decimal128(contract['balance'])
                        else:
                            contract['balance'] = Decimal128('0')
                        #print(contract['balance'])

                        if "<span title='Normal Transactions' rel='tooltip' data-placement='bottom'>" in webpage:
                            contract['nrOfTransactions'] = int(re.compile("<span title='Normal Transactions' rel='tooltip' data-placement='bottom'>(.+?) txn.*?</span>").findall(webpage)[0])
                        elif "<span title='' rel='tooltip' data-placement='bottom' data-original-title='Normal Transactions'>" in webpage:
                            contract['nrOfTransactions'] = int(re.compile("<span title='' rel='tooltip' data-placement='bottom' data-original-title='Normal Transactions'>(.+?) txn(.*?) </span>").findall(webpage)[0])
                        #print("Nr Of Transactions: "+str(token['nrOfTransactions']))

                        #if "pre class='wordwrap js-copytextarea2' id='js-copytextarea2'" in webpage:
                        contract['abi'] = re.compile("<pre class='wordwrap js-copytextarea2' id='js-copytextarea2' style='.+?'>([\s\S]+?)</pre>", re.MULTILINE).findall(webpage)[0]
                        #print("ABI: "+str(token['abi']))

                        contract['byteCode'] = web3.eth.getCode(web3.toChecksumAddress(contract['address'])).hex().replace("0x", "")
                        #print("Byte Code: "+str(contract['byteCode']))

                        collection.insert_one(contract)
                        # Indexing...
                        if 'address' not in collection.index_information():
                            collection.create_index('address', unique=True)
                            collection.create_index('balance')
                            collection.create_index('contractName')
                            collection.create_index('nrOfTransactions')
                            collection.create_index('compilerVersion')
                            collection.create_index('optimizationEnabled')
                            collection.create_index('optimizerRuns')

                        if contract['byteCode'] == "":
                            print("Bytecode is missing for contract: "+str(contract['address']))

                        success = True
                    except Exception as e:
                        if "Request Throttled" in webpage:
                            print("Request throttled contract address "+contract['address'])
                        else:
                            print("Unexpected error at contract address "+contract['address']+": "+str(e))
                            #traceback.print_exc()
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
    q = queue.Queue()

    # Create new threads
    threads = []
    threadID = 1
    for i in range(5):
        collection = MongoClient('127.0.0.1', 27017)['ethereum']['zeus_contracts']
        scraper = cfscrape.CloudflareScraper()
        thread = searchThread(threadID, q, collection, scraper)
        thread.start()
        threads.append(thread)
        threadID += 1

    # Fill the queue with contract objects
    queueLock.acquire()
    with open('zeus_dataset.csv') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        for row in reader:
            contract = {}
            contract['address'] = str(row[1].split('_')[-1]).lower()
            if not contract['address'].startswith('0x'):
                contract['address'] = "0x" + contract['address']
            q.put(contract)
    queueLock.release()

    print('Searching for '+str(q.qsize())+' contracts...\n')

    # Wait for queue to empty
    while not q.empty():
        pass

    # Notify threads it's time to exit
    exitFlag = 1

    # Wait for all threads to complete
    for t in threads:
       t.join()

    print('\nDone')
