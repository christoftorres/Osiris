#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import json
import csv
import math

from collections import Counter

FOLDER = "zeus_results"

global total
global vulnearable
global time
global paths
global min_paths
global max_paths
global nr_contracts
global coverage
global timeouts
global timeouts_array

global overflows
global underflows

global safe
global unsafe

total        = 0
vulnearable  = 0
time         = 0.0
time_array   = []
paths        = 0
min_paths    = 0
max_paths    = 0
nr_contracts = 0
coverage     = 0.0
timeouts     = 0
timeouts_array = []

overflows    = 0
underflows   = 0

safe         = set()
unsafe       = set()

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
    global timeouts_array

    global overflows
    global underflows

    global overflow
    global underflow

    global timeout

    if contract["overflow"] != False:
        overflow = True
    if contract["underflow"] != False:
        underflow = True

    if contract["timeout"] != False:
        timeout = True

    if overflow or underflow:
        vulnearable += 1

    time += float(contract["execution_time"])
    time_array.append(round(float(contract["execution_time"])))
    paths += int(contract["execution_paths"])
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

            global timeout

            overflow    = False
            underflow   = False

            timeout     = False

            if not "evm_code_coverage" in data:
                for contract in data:
                    evaluate_contract(data[contract])
            else:
                evaluate_contract(data)

            if overflow:
                overflows += 1
                #print os.path.join(os.path.join("..", FOLDER), file)
            if underflow:
                underflows += 1
                #print os.path.join(os.path.join("..", FOLDER), file)

            address = file.split('x')[1].split('.')[0]

            if overflow or underflow:
                unsafe.add(address)
            else:
                safe.add(address)

            if timeout:
                timeouts += 1
                timeouts_array.append(address)
        except Exception as e:
            print " --> Exception in: "+os.path.join(os.path.join("..", FOLDER), file)
            print "Reason: "+str(e)

print "Number of analyzed contracts: "+str(total)
print "Total execution time: "+str(time)+" seconds, avg: "+str(float(time)/float(nr_contracts))+" seconds"
print Counter(time_array).most_common(2)
print median(time_array)
print variance(time_array)
print standard_deviation(time_array)
print "Average code coverage: "+str(float(coverage)/float(nr_contracts))+"%"
print "Number of explored paths: "+str(paths)+", min: "+str(min_paths)+", max: "+str(max_paths)+", avg: "+str(float(paths)/float(nr_contracts))
print "Number of vulnearable contracts: "+str(vulnearable)+" ("+str(float(vulnearable)/float(total)*100)+"%)"
print "Number of timeouts: "+str(timeouts)
print "====================================================================="
print "Number of overflows: "+str(overflows)+" ("+str(float(overflows)/float(total)*100)+"%)"
print "Number of underflows: "+str(underflows)+" ("+str(float(underflows)/float(total)*100)+"%)"

print "Safe contracts: "+str(len(safe))
print "Unsafe contracts: "+str(len(unsafe))

print "ZEUS:"
zeus_safe = []
zeus_unsafe = []
zeus_errors = []
zeus_timeouts = []
for address in list(set().union(safe,unsafe)):
    with open('zeus_dataset.csv') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        for row in reader:
            if str(address[:-1]).lower() in str(row[1]).lower():
                if row[2] == 'Verif_err':
                    if not address in zeus_errors:
                        zeus_errors.append(address)
                elif row[2] == 'Timeout_Verifier':
                    if not address in zeus_timeouts:
                        zeus_timeouts.append(address)
                elif row[2] == 'Safe':
                    if not address in zeus_safe:
                        zeus_safe.append(address)
                elif row[2] == 'Unsafe':
                    if not address in zeus_unsafe:
                        zeus_unsafe.append(address)
                break
print "Safe: "+str(len(zeus_safe))
print "Unsafe: "+str(len(zeus_unsafe))
print "Errors: "+str(len(zeus_errors))
print "Timeout: "+str(len(zeus_timeouts))
print "-----"
print len(zeus_safe)+len(zeus_unsafe)+len(zeus_errors)+len(zeus_timeouts)


"""results = []
results.append(['Address', 'Osiris', '', 'Zeus', '', ''])
for file in os.listdir(os.path.join("..", FOLDER)):
    if file.endswith(".json"):
        row = []
        address = file.split('x')[1].split('.')[0]
        row.append('0x'+str(address))
        if address in safe:
            row.append('Safe')
        elif address in unsafe:
            row.append('Unsafe')
        else:
            row.append('')
            print("ERROR: "+str(address)+" not found in Safe or Unsafe set")
        row.append('')
        found = False
        with open('zeus_dataset.csv') as csvfile:
            reader = csv.reader(csvfile, delimiter=';')
            for zeus_row in reader:
                if str(address[:-1]).lower() in str(zeus_row[1]).lower() and not found:
                    found = True
                    row.append(str(zeus_row[2]))
                    row.append(str(zeus_row[3]))
        if not found:
            print "Error not found: "+str(address)
        results.append(row)
with open('zeus_comparison.csv', 'wb') as results_file:
    writer = csv.writer(results_file, delimiter=',')
    for result in results:
        writer.writerow(result)"""

# Check for unsafe/safe contracts

print ""
print "Cases where Osiris finds 'safe' and Zeus finds 'safe'"
matches = []
for address in safe:
    found = False
    with open('zeus_dataset.csv') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        for row in reader:
            if str(address[:-1]).lower() in str(row[1]).lower():
                found = True
                if row[2] == 'Safe':
                    if address not in matches:
                        matches.append(address)
                    #print ""
                    #print "Osiris: "+str(address)+" Safe"
                    #print "Zeus: "+str(row[1])+" "+str(row[2])+" "+str(row[3])
                break
    if not found:
        print "Error not found: "+str(address)
print ""
print len(matches)


print ""
print "Cases where Osiris finds 'unsafe' while Zeus finds 'safe'"
mismatches = []
for address in unsafe:
    found = False
    with open('zeus_dataset.csv') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        for row in reader:
            if str(address[:-1]).lower() in str(row[1]).lower():
                found = True
                if row[2] == 'Safe':
                    if address not in mismatches:
                        mismatches.append(address)
                    print ""
                    print "Osiris: "+str(address)+" Unsafe"
                    print "Zeus: "+str(row[1])+" "+str(row[2])+" "+str(row[3])
                break
    if not found:
        print "Error not found: "+str(address)
print ""
print len(mismatches)

print ""
print "Cases where Osiris finds 'safe' and Zeus finds 'no result'"
matches = []
for address in safe:
    found = False
    with open('zeus_dataset.csv') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        for row in reader:
            if str(address[:-1]).lower() in str(row[1]).lower():
                found = True
                if row[2] != 'Safe' and row[2] != 'Unsafe':
                    if address not in matches:
                        matches.append(address)
                    #print ""
                    #print "Osiris: "+str(address)+" Safe"
                    #print "Zeus: "+str(row[1])+" "+str(row[2])+" "+str(row[3])
                break
    if not found:
        print "Error not found: "+str(address)
print ""
print len(matches)

print ""
print "Cases where Osiris finds 'unsafe' and Zeus finds 'unsafe'"
matches = []
for address in unsafe:
    found = False
    with open('zeus_dataset.csv') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        for row in reader:
            if str(address[:-1]).lower() in str(row[1]).lower():
                found = True
                if row[2] == 'Unsafe':
                    if address not in matches:
                        matches.append(address)
                    #print ""
                    #print "Osiris: "+str(address)+" Safe"
                    #print "Zeus: "+str(row[1])+" "+str(row[2])+" "+str(row[3])
                break
    if not found:
        print "Error not found: "+str(address)
print ""
print len(matches)

print ""
print "Cases where Osiris finds 'unsafe' and Zeus finds 'no result'"
matches = []
for address in unsafe:
    found = False
    with open('zeus_dataset.csv') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        for row in reader:
            if str(address[:-1]).lower() in str(row[1]).lower():
                found = True
                if row[2] != 'Safe' and row[2] != 'Unsafe':
                    if address not in matches:
                        matches.append(address)
                    #print ""
                    #print "Osiris: "+str(address)+" Safe"
                    #print "Zeus: "+str(row[1])+" "+str(row[2])+" "+str(row[3])
                break
    if not found:
        print "Error not found: "+str(address)
print ""
print len(matches)

print ""
print "Cases where Osiris finds 'safe' while Zeus finds 'unsafe'"
mismatches = []
for address in safe:
    found = False
    with open('zeus_dataset.csv') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        for row in reader:
            if str(address[:-1]).lower() in str(row[1]).lower():
                found = True
                if row[2] == 'Unsafe':
                    if address not in mismatches:
                        mismatches.append(address)
                    #print ""
                    #print "Osiris: "+str(address)+" Safe"
                    #print "Zeus: "+str(row[1])+" "+str(row[2])+" "+str(row[3])
                break
    if not found:
        print "Error not found: "+str(address)
print ""
print len(mismatches)

"""
print ""
print "Cases where Zeus does not find a result"
mismatches = []
for address in list(set().union(safe,unsafe)):
    found = False
    with open('zeus_dataset.csv') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        for row in reader:
            if str(address[:-1]).lower() in str(row[1]).lower():
                found = True
                if row[2] != 'Unsafe' and row[2] != 'Safe':
                    if address not in mismatches:
                        mismatches.append(address)
                    print ""
                    if address in safe:
                        print "Osiris: "+str(address)+" Safe"
                    else:
                        print "Osiris: "+str(address)+" Unsafe"
                    print "Zeus: "+str(row[1])+" "+str(row[2])+" "+str(row[3])
                    if address in timeouts_array:
                        print "Timeout"
                    else:
                        print "No Timeout"
    if not found:
        print "Error not found: "+str(address)
print ""
print len(mismatches)
"""

print ""
print "Cases where Zeus produces incorrect results"
mismatches = []
false_positives = []
for address in list(set().union(safe,unsafe)):
    found = False
    with open('zeus_dataset.csv') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        for row in reader:
            if str(address[:-1]).lower() in str(row[1]).lower():
                found = True
                if row[3] == 'Incorrect':
                    if address not in mismatches:
                        mismatches.append(address)
                    print ""
                    if address in safe:
                        print "Osiris: "+str(address)+" Safe"
                    else:
                        print "Osiris: "+str(address)+" Unsafe"
                    if address in safe and row[2] == 'Unsafe':
                        false_positives.append(address)
                    if address in unsafe and row[2] == 'Safe':
                        false_positives.append(address)
                    print "Zeus: "+str(row[1])+" "+str(row[2])+" "+str(row[3])
                    if address in timeouts_array:
                        print "Timeout"
                    else:
                        print "No Timeout"
    if not found:
        print "Error not found: "+str(address)
print ""
print str(len(false_positives))+"/"+str(len(mismatches))
print float(len(false_positives))/float(len(mismatches))*100.0

"""
for address in unsafe:
    found = False
    with open('zeus_dataset.csv') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        for row in reader:
            if str(address[:-1]).lower() in str(row[1]).lower():
                found = True
                if row[2] == 'Unsafe' and row[3] == 'Incorrect':
                    if address not in mismatches:
                        mismatches.append(address)
                    print "mismatch"
                    print "Osiris: "+str(address)+" Unsafe"
                    print "Zeus: "+str(row[1])+" "+str(row[2])+" "+str(row[3])

    if not found:
        print "Error not found: "+str(address)

print ""

"""
