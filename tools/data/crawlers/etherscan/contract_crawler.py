#!/usr/bin/python
# -*- coding: utf-8 -*-

import Queue
import threading
import pymongo
import datetime

from opcodes import *
from web3 import Web3, KeepAliveRPCProvider
from bson.decimal128 import Decimal128
from pymongo import MongoClient

web3 = Web3(KeepAliveRPCProvider(host='127.0.0.1', port='8545'))
latestBlock = web3.eth.getBlock('latest')
exitFlag = 0

nrOfTransactions = {}

def init():
    if web3.eth.syncing == False:
        print('Ethereum blockchain is up-to-date.')
        print('Latest block: '+str(latestBlock.number)+' ('+datetime.datetime.fromtimestamp(int(latestBlock.timestamp)).strftime('%d-%m-%Y %H:%M:%S')+')\n')
    else:
        print('Ethereum blockchain is currently syncing...')
        print('Latest block: '+str(latestBlock.number)+' ('+datetime.datetime.fromtimestamp(int(latestBlock.timestamp)).strftime('%d-%m-%Y %H:%M:%S')+')\n')

class searchThread(threading.Thread):
   def __init__(self, threadID, queue, collection):
      threading.Thread.__init__(self)
      self.threadID = threadID
      self.queue = queue
      self.collection = collection
   def run(self):
      searchContract(self.queue, self.collection)

def searchContract(queue, collection):
    while not exitFlag:
        queueLock.acquire()
        if not queue.empty():
            blockNumber = queue.get()
            queueLock.release()
            print('Searching block '+str(blockNumber)+' for contracts...')
            block = web3.eth.getBlock(blockNumber, True)
            if block and block.transactions:
                for transaction in block.transactions:
                    if not transaction.to:
                        receipt = web3.eth.getTransactionReceipt(transaction.hash)
                        result = collection.find({'address': receipt['contractAddress']})
                        print('Contract found: '+receipt['contractAddress'])
                        if result.count() == 0:
                            transaction_input = transaction['input'].replace("0x", "")
                            contract_code = web3.eth.getCode(receipt['contractAddress']).replace("0x", "")
                            # Uncomment this line if you want to skip zombie contracts
                            #if len(transaction_input) == 0 and len(contract_code) == 0:
                            #    print('Contract '+receipt['contractAddress']+' is empty...')
                            #    continue
                            contract = {}
                            contract['address'] = receipt['contractAddress']
                            contract['transactionHash'] = transaction['hash']
                            contract['blockNumber'] = transaction['blockNumber']
                            contract['timestamp'] = block.timestamp
                            contract['creator'] = transaction['from']
                            contract['input'] = transaction_input
                            contract['byteCode'] = contract_code
                            contract['balance'] = web3.fromWei(web3.eth.getBalance(contract['address']), 'ether')
                            if not contract['balance'] == 0:
                                contract['balance'] = Decimal128(contract['balance'])
                            else:
                                contract['balance'] = Decimal128('0')
                            contract['nrOfTransactions'] = 0
                            instructions = getInstructions(contract_code)
                            contract['nrOfInstructions'] = len(instructions)
                            contract['nrOfDistinctInstructions'] = len(set(instructions))
                            collection.insert_one(contract)
                            # Indexing...
                            if 'address' not in collection.index_information():
                                collection.create_index('address', unique=True)
                                collection.create_index('transactionHash', unique=True)
                                collection.create_index('blockNumber')
                                collection.create_index('timestamp')
                                collection.create_index('creator')
                                collection.create_index('balance')
                                collection.create_index('nrOfTransactions')
                                collection.create_index('nrOfInstructions')
                                collection.create_index('nrOfDistinctInstructions')
                            print('Contract '+contract['address']+' has been successfully added.')
                        else:
                            print('Contract '+receipt['contractAddress']+' already exists...')
                    transactionLock.acquire()
                    if transaction['from'] in nrOfTransactions:
                        nrOfTransactions[transaction['from']] += 1
                    else:
                        nrOfTransactions[transaction['from']] = 1
                    if transaction['to'] in nrOfTransactions:
                        nrOfTransactions[transaction['to']] += 1
                    else:
                        nrOfTransactions[transaction['to']] = 1
                    transactionLock.release()
        else:
            queueLock.release()

def getInstructions(byteCode):
    code = bytearray.fromhex(byteCode)
    pc = 0
    instructions = []
    while pc < len(code):
        try:
            currentOpCode = opcodes[code[pc]][0]
            instructions.append(currentOpCode)
            if (currentOpCode[0:4] == 'PUSH'):
                pc += int(currentOpCode[4:])
        except Exception:
            instructions.append('INVALID OPCODE '+hex(code[pc]))
            pass
        pc += 1
    return instructions

if __name__ == "__main__":
    init()

    transactionLock = threading.Lock()

    queueLock = threading.Lock()
    queue = Queue.Queue()

    # Create new threads
    threads = []
    threadID = 1
    for i in range(1000):
        collection = MongoClient('127.0.0.1', 27017)['ethereum']['contracts']
        thread = searchThread(threadID, queue, collection)
        thread.start()
        threads.append(thread)
        threadID += 1

    startBlockNumber = 0
    #cursor = MongoClient('127.0.0.1', 27017)['ethereum']['contracts'].find().sort('blockNumber', pymongo.DESCENDING).limit(1)
    #for contract in cursor:
    #    startBlockNumber = contract['blockNumber']
    #endBlockNumber = max(startBlockNumber, latestBlock.number)
    endBlockNumber = 5000000

    # Fill the queue with block numbers
    queueLock.acquire()
    for i in range(startBlockNumber, endBlockNumber+1):
        queue.put(i)
    queueLock.release()

    print('Searching for contracts within blocks '+str(startBlockNumber)+' and '+str(endBlockNumber)+'\n')

    # Wait for queue to empty
    while not queue.empty():
        pass

    # Notify threads it's time to exit
    exitFlag = 1

    # Wait for all threads to complete
    for t in threads:
       t.join()

    # Copy number of transactions to database
    collection = MongoClient('127.0.0.1', 27017)['ethereum']['contracts']
    cursor = collection.find()
    for contract in cursor:
        if contract['address'] in nrOfTransactions:
            contract['nrOfTransactions'] = nrOfTransactions[contract['address']]
            collection.save(contract)

    print('\nDone')
