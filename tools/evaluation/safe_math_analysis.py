#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import json
import pymongo
import os.path

from pymongo import MongoClient
from html.parser import HTMLParser

FINDINGS = "tokens_results"

MONGO_HOST      = '127.0.0.1'
MONGO_PORT      = 27017
DATABASE        = 'ethereum'
COLLECTION      = 'tokens'

collection = MongoClient(MONGO_HOST, MONGO_PORT)[DATABASE][COLLECTION]
parser = HTMLParser()
cursor = collection.find()
total = cursor.count()
print(total)
counter = 0
addresses = []
for contract in cursor:
    code = parser.unescape(contract['sourceCode'])
    if "SafeMath" in code:
        counter += 1
        addresses.append(contract['address'])
print(counter)
percentage = counter/total*100
print(percentage)
print(100-percentage)
counter2 = 0
for file in os.listdir(os.path.join("..", FINDINGS)):
    if file.endswith(".json"):
        address = file.split('.')[0]
        data = json.load(open(os.path.join(os.path.join("..", FINDINGS), file)))
        if data["overflow"] or data["underflow"] or data["division"]:
            for addr in addresses:
                if address == addr:
                    counter2 += 1
                    break
print(counter2)
percentage2 = counter2/counter*100
print(percentage2)
print(100-percentage2)
