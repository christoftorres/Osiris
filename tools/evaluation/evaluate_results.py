#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import json
import pymongo
import os.path
import traceback
import math

from collections import Counter

from pymongo import MongoClient
from html.parser import HTMLParser

FOLDER = "million_results"

MONGO_HOST      = '127.0.0.1'
MONGO_PORT      = 27017
DATABASE        = 'ethereum'
COLLECTION      = 'contracts'

def mean(x):
    return sum(x) / len(x)

def median(x):
    # Input: list of numbers; Output: the "middle" number of an ordered list of #s

    sorted_x = sorted(x)
    length_n = len(x)

    middle = length_n // 2 # Integer division

    # Even numbered amount in list:
    if length_n % 2 == 0:
        median_even = (sorted_x[middle - 1] + sorted_x[middle]) / 2
        return(median_even) # Remember index 0 as 1st element.
    else:
        return(sorted_x[middle]) # Return middle number

def variance(x):
     n = len(x)
     x_bar = mean(x)
     return(round(sum((x_i - x_bar)**2 for x_i in x) / (n - 1), 2))

def standard_deviation(x):
     return(math.sqrt(variance(x)))


global total
global vulnearable
global time
global paths
global min_paths
global max_paths
global nr_contracts
global coverage
global timeouts

global overflows
global underflows
global divisions
global modulos
global signednesses
global truncations

global list_of_overflows
global list_of_underflows
global list_of_divisions
global list_of_modulos
global list_of_signedness
global list_of_truncations
global list_of_arithmetic

global timestamps
global assertions
global callstacks
global reentrancies
global moneyflows

total        = 0
vulnearable  = 0
time         = 0.0
time_array   = []
paths        = 0
min_paths    = 0
max_paths    = 0
paths_array = []
nr_contracts = 0
coverage     = 0.0
timeouts     = 0

overflows    = 0
underflows   = 0
divisions    = 0
modulos      = 0
signednesses = 0
truncations  = 0


list_of_overflows = set()
list_of_underflows = set()
list_of_divisions = set()
list_of_modulos = set()
list_of_signedness = set()
list_of_truncations = set()
list_of_arithmetic = set()

timestamps   = 0
assertions   = 0
callstacks   = 0
reentrancies = 0
moneyflows   = 0

addresses    = set()

def evaluate_contract(contract):
    global total
    global vulnearable
    global time
    global time_array
    global paths
    global min_paths
    global max_paths
    global nr_contracts
    global coverage
    global timeouts
    global paths_array

    global overflows
    global underflows
    global divisions
    global modulos
    global signednesses
    global truncations

    global timestamps
    global assertions
    global callstacks
    global reentrancies
    global moneyflows

    global list_of_overflows
    global list_of_underflows
    global list_of_divisions
    global list_of_modulos
    global list_of_signedness
    global list_of_truncations
    global list_of_arithmetic

    global overflow
    global underflow
    global division
    global modulo
    global signedness
    global truncation

    global timestamp
    global assertion
    global callstack
    global reentrancy
    global moneyflow

    global timeout

    if contract["overflow"] != False:
        overflow = True
    if contract["underflow"] != False:
        underflow = True
    if contract["division"] != False:
        division = True
    if contract["modulo"] != False:
        modulo = True
    if contract["truncation"] != False:
        truncation = True
    if contract["signedness"] != False:
        signedness = True

    if contract["time_dependency"] != False:
        timestamp = True
    if contract["assertion_failure"] != False:
        assertion = True
    if contract["reentrancy"] != False:
        callstack = True
    if contract["callstack"] != False:
        reentrancy = True
    if contract["money_concurrency"] != False:
        moneyflow = True

    if contract["timeout"] != False:
        timeout = True

    if contract["execution_time"] != "":
        time += float(contract["execution_time"])
        time_array.append(round(float(contract["execution_time"])))
    paths += int(contract["execution_paths"])
    paths_array.append(int(contract["execution_paths"]))
    coverage += float(contract["evm_code_coverage"])
    nr_contracts += 1
    if min_paths == 0 or int(contract["execution_paths"]) < min_paths:
        min_paths = int(contract["execution_paths"])
    if max_paths == 0 or int(contract["execution_paths"]) > max_paths:
        max_paths = int(contract["execution_paths"])

print("Evaluating results...")

for file in os.listdir(os.path.join("..", FOLDER)):
    if file.endswith(".json"):
        total += 1
        try:
            data = json.load(open(os.path.join(os.path.join("..", FOLDER), file)))

            global overflow
            global underflow
            global division
            global modulo
            global signedness
            global truncation

            global timestamp
            global assertion
            global callstack
            global reentrancy
            global moneyflow

            global timeout

            overflow    = False
            underflow   = False
            division    = False
            modulo      = False
            signedness  = False
            truncation  = False

            timestamp   = False
            assertion   = False
            callstack   = False
            reentrancy  = False
            moneyflow   = False

            timeout     = False

            if not "evm_code_coverage" in data:
                for contract in data:
                    evaluate_contract(data[contract])
            else:
                evaluate_contract(data)

            address = file.split('.')[0]

            if overflow:
                overflows += 1
                list_of_overflows.add(address)
                #print(os.path.join(os.path.join("..", FOLDER), file))
            if underflow:
                underflows += 1
                list_of_underflows.add(address)
                #print(os.path.join(os.path.join("..", FOLDER), file))
            if division:
                divisions += 1
                list_of_divisions.add(address)
                #print(os.path.join(os.path.join("..", FOLDER), file))
            if modulo:
                modulos += 1
                list_of_modulos.add(address)
                #print(os.path.join(os.path.join("..", FOLDER), file))
            if signedness:
                signednesses += 1
                list_of_signedness.add(address)
                #print(os.path.join(os.path.join("..", FOLDER), file))
            if truncation:
                truncations += 1
                list_of_truncations.add(address)
                #print(os.path.join(os.path.join("..", FOLDER), file))
            if overflow or underflow or division or modulo:
                list_of_arithmetic.add(address)
            if overflow or underflow or division or modulo or signedness or truncation:
                vulnearable += 1
                addresses.add(address)

            if timestamp:
                timestamps += 1
            if assertion:
                assertions += 1
            if callstack:
                callstacks += 1
            if reentrancy:
                reentrancies += 1
            if moneyflow:
                moneyflows += 1

            if timeout:
                timeouts += 1
        except Exception as e:
            print(" --> Exception in: "+os.path.join(os.path.join("..", FOLDER), file))
            print("Reason: "+str(e))
            traceback.print_exc()

print("Number of analyzed contracts: "+str(total))
print("Total execution time: "+str(time)+" seconds, avg: "+str(float(time)/float(nr_contracts))+" seconds")
data = Counter(time_array)
print(data.most_common(1))
print(median(time_array))
#print(variance(time_array))
#print(standard_deviation(time_array))
print("Average code coverage: "+str(float(coverage)/float(nr_contracts))+"%")
print("Number of explored paths: "+str(paths)+", min: "+str(min_paths)+", max: "+str(max_paths)+", avg: "+str(float(paths)/float(nr_contracts)))
data = Counter(paths_array)
print(data.most_common(1))
print(median(paths_array))
print("Number of vulnearable contracts: "+str(vulnearable))
print("Number of timeouts: "+str(timeouts))
print("=====================================================================")
print("Number of overflows: "+str(overflows)+" ("+str(float(overflows)/float(total)*100)+"%)")
print("Number of underflows: "+str(underflows)+" ("+str(float(underflows)/float(total)*100)+"%)")
print("Number of divisions: "+str(divisions)+" ("+str(float(divisions)/float(total)*100)+"%)")
print("Number of modulos: "+str(modulos)+" ("+str(float(modulos)/float(total)*100)+"%)")
print("Number of signednesses: "+str(signednesses)+" ("+str(float(signednesses)/float(total)*100)+"%)")
print("Number of truncations: "+str(truncations)+" ("+str(float(truncations)/float(total)*100)+"%)")
print("=====================================================================")
print("Number of timestamps: "+str(timestamps)+" ("+str(float(timestamps)/float(total)*100)+"%)")
print("Number of assertions: "+str(assertions)+" ("+str(float(assertions)/float(total)*100)+"%)")
print("Number of callstacks: "+str(callstacks)+" ("+str(float(callstacks)/float(total)*100)+"%)")
print("Number of reentrancies: "+str(reentrancies)+" ("+str(float(reentrancies)/float(total)*100)+"%)")
print("Number of moneyflows: "+str(moneyflows)+" ("+str(float(moneyflows)/float(total)*100)+"%)")

collection = MongoClient(MONGO_HOST, MONGO_PORT)[DATABASE][COLLECTION]

########################################################################

print("list of modulos: "+str(len(list_of_modulos)))

print(len(list_of_arithmetic))
print("")
list_of_bytecode_addresses = set()
list_of_bytecode_overflows = set()
list_of_bytecode_underflows = set()
list_of_bytecode_divisions = set()
list_of_bytecode_modulos = set()
list_of_bytecode_truncations = set()
list_of_bytecode_signedness = set()
list_of_bytecode_arithmetic = set()
cursor = collection.find()
for contract in cursor:
    if contract["address"] in addresses:
        list_of_bytecode_addresses.add(contract["byteCode"].encode('utf-8'))
    if contract["address"] in list_of_overflows:
        list_of_bytecode_overflows.add(contract["byteCode"].encode('utf-8'))
    if contract["address"] in list_of_underflows:
        list_of_bytecode_underflows.add(contract["byteCode"].encode('utf-8'))
    if contract["address"] in list_of_divisions:
        list_of_bytecode_divisions.add(contract["byteCode"].encode('utf-8'))
    if contract["address"] in list_of_modulos:
        list_of_bytecode_modulos.add(contract["byteCode"].encode('utf-8'))
    if contract["address"] in list_of_truncations:
        list_of_bytecode_truncations.add(contract["byteCode"].encode('utf-8'))
    if contract["address"] in list_of_signedness:
        list_of_bytecode_signedness.add(contract["byteCode"].encode('utf-8'))
    if contract["address"] in list_of_arithmetic:
        list_of_bytecode_arithmetic.add(contract["byteCode"].encode('utf-8'))
if len(addresses) != len(list_of_bytecode_addresses):
    print("Error")
if len(list_of_overflows) != len(list_of_bytecode_overflows):
    print("Error")
if len(list_of_underflows) != len(list_of_bytecode_underflows):
    print("Error")
if len(list_of_divisions) != len(list_of_bytecode_divisions):
    print("Error")
if len(list_of_modulos) != len(list_of_bytecode_modulos):
    print("Error")
if len(list_of_truncations) != len(list_of_bytecode_truncations):
    print("Error")
if len(list_of_signedness) != len(list_of_bytecode_signedness):
    print("Error")
if len(list_of_arithmetic) != len(list_of_bytecode_arithmetic):
    print("Error")
million_addresses = 0
million_overflows = 0
million_underflows = 0
million_divisions = 0
million_modulos = 0
million_truncations = 0
million_signedness = 0
million_arithmetic = 0
cursor = collection.find()
for contract in cursor:
    if contract["byteCode"].encode('utf-8') in list_of_bytecode_addresses:
        million_addresses += 1
    if contract["byteCode"].encode('utf-8') in list_of_bytecode_overflows:
        million_overflows += 1
    if contract["byteCode"].encode('utf-8') in list_of_bytecode_underflows:
        million_underflows += 1
    if contract["byteCode"].encode('utf-8') in list_of_bytecode_divisions:
        million_divisions += 1
    if contract["byteCode"].encode('utf-8') in list_of_bytecode_modulos:
        million_modulos += 1
    if contract["byteCode"].encode('utf-8') in list_of_bytecode_truncations:
        million_truncations += 1
    if contract["byteCode"].encode('utf-8') in list_of_bytecode_signedness:
        million_signedness += 1
    if contract["byteCode"].encode('utf-8') in list_of_bytecode_arithmetic:
        million_arithmetic += 1
print("Overall: "+str(million_addresses))
print("Overflows: "+str(million_overflows))
print("Underflows: "+str(million_underflows))
print("Divisions: "+str(million_divisions))
print("Modulos: "+str(million_modulos))
print("Truncations: "+str(million_truncations))
print("Signedness: "+str(million_signedness))
print("Arithmetic: "+str(million_arithmetic))
