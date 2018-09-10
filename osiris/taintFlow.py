import re
import copy
import traceback
import global_params

from utils import *
from opcodes import *
from intFlow import *
from vargenerator import *

SOURCES = set(['CALLDATALOAD', 'CALLDATACOPY', 'CALLVALUE', 'SLOAD'])
SINKS   = set(['SSTORE', 'JUMPI', 'RETURN', 'CALL'])

global branches
branches = {}

global tainted_stack
tainted_stack = []

global tainted_memory
tainted_memory = {}

global tainted_storage
tainted_storage = {}

global storage_flows
storage_flows = []

global sink_flows
sink_flows = []

global sha3_list
sha3_list = set()

global false_positives
false_positives = []

global strings
strings = set()

class TaintObject:
    def __init__(self, _data, _taint=None):
        self.data  = _data
        self.taint = _taint
    def __str__(self):
        string = '{'
        string += '"data": "'+str(self.data)+'",'
        string += '"taint": "'+str(self.taint)+'"'
        string += '}'
        return string
    def __eq__(self, _other):
        return self.__dict__ == _other.__dict__

class InstructionObject:
    def __init__(self, _opcode, _data_in, _data_out):
        self.opcode = _opcode
        self.data_in = _data_in
        self.data_out = _data_out
    def __str__(self):
        string = '{'
        string += '"opcode":"'+str(self.opcode)+'",'
        string += '"data_in":['
        for i, data in enumerate(self.data_in):
            if i:
                string += ","
            string += '"'+remove_line_break_space(data)+'"'
        string += '],'
        string += '"data_out":['
        for i, data in enumerate(self.data_out):
            if i:
                string += ","
            string += '"'+remove_line_break_space(data)+'"'
        string += ']'
        string += '}'
        return string
    def __eq__(self, _other):
        if _other.__class__.__name__ == "InstructionObject":
            return self.__dict__ == _other.__dict__
        else:
            return False

def init_taint_analysis():
    global branches
    global tainted_stack
    global tainted_memory
    global tainted_storage
    global storage_flows
    global sink_flows
    global sha3_list
    global false_positives
    global strings

    branches = {}
    tainted_stack = []
    tainted_memory = {}
    tainted_storage = {}
    storage_flows = []
    sink_flows = []
    sha3_list = set()
    false_positives = []
    strings = set()

def introduce_taint(instruction, pc, arithmetic_errors):
    taint = None
    if instruction.opcode in SOURCES:
        if not taint:
            taint = []
        taint.append(instruction)
    for arithmetic_error in arithmetic_errors:
        if arithmetic_error["pc"] == pc:
            if not taint:
                taint = []
            taint.append(arithmetic_error)
    if global_params.DEBUG_MODE and taint:
        if taint:
            print "Introducing taint: "
            for object in taint:
                print " --> "+str(object)
    return taint

def propagate_taint(taint, tainted_stack, tainted_memory, tainted_storage, instruction, current_stack, previous_block, current_block, next_blocks, arithmetic_errors, sha3_list, false_positives, strings):
    # Handle PUSHs
    if "PUSH" in instruction.opcode:
        tainted_stack.insert(0, TaintObject(current_stack[0], taint))

    # Hanlde DUPs
    elif "DUP" in instruction.opcode:
        object = tainted_stack[len(instruction.data_in)-1]
        if object.__class__.__name__ == "TaintObject":
            tainted_stack.insert(0, object)
        else:
            tainted_stack.insert(0, TaintObject(object, taint))

    # Handle SWAPs
    elif "SWAP" in instruction.opcode:
        temp = tainted_stack[len(instruction.data_in)-1]
        tainted_stack[len(instruction.data_in)-1] = tainted_stack[0]
        tainted_stack[0] = temp

    # Handle memory
    elif "MSTORE" in instruction.opcode:
        address = tainted_stack.pop(0).data
        value = tainted_stack.pop(0)
        tainted_memory[address] = value
    elif "MLOAD" == instruction.opcode:
        address = tainted_stack.pop(0).data
        if not address in tainted_memory:
            tainted_memory[address] = TaintObject(current_stack[0], taint)
        value = tainted_memory[address]
        tainted_stack.insert(0, value)

    # Handle storage
    elif "SSTORE" == instruction.opcode:
        address = tainted_stack.pop(0).data
        value = tainted_stack.pop(0)
        tainted_storage[address] = value
    elif "SLOAD" == instruction.opcode:
        address = tainted_stack.pop(0).data
        if not address in tainted_storage:
            if global_params.INTERPROCEDURAL_TAINT:
                tainted_storage[address] = TaintObject(current_stack[0], [instruction])
            else:
                tainted_storage[address] = TaintObject(current_stack[0], taint)
        value = tainted_storage[address]
        tainted_stack.insert(0, value)

    # Hanlde SHA3
    elif instruction.opcode == "SHA3":
        s0 = tainted_stack.pop(0).data
        s1 = tainted_stack.pop(0).data
        sha3_taint = []
        if not isAllReal(s1, s0):
            if s0 in tainted_memory:
                object = tainted_memory[s0]
                if object.taint:
                    for tainted_object in object.taint:
                        sha3_taint.append(tainted_object)
        else:
            for i in range(s1/32):
                address = s0+i*32
                if address in tainted_memory:
                    object = tainted_memory[address]
                    if object.taint:
                        for tainted_object in object.taint:
                            sha3_taint.append(tainted_object)
        if len(sha3_taint) == 0:
            tainted_stack.insert(0, TaintObject(current_stack[0], None))
        else:
            tainted_stack.insert(0, TaintObject(current_stack[0], sha3_taint))
        if not current_stack[0] in sha3_list:
            sha3_list.add(current_stack[0])

    # Handle CALLDATACOPY and CODECOPY and RETURNDATACOPY
    elif "CALLDATACOPY" == instruction.opcode or "CODECOPY" == instruction.opcode or "RETURNDATACOPY" == instruction.opcode:
        address = tainted_stack.pop(0).data
        tainted_stack.pop(0)
        tainted_memory[address] = tainted_stack.pop(0)

    # Handle EXTCODECOPY
    elif "EXTCODECOPY" == instruction.opcode:
        tainted_stack.pop(0)
        address = tainted_stack.pop(0).data
        tainted_stack.pop(0)
        tainted_memory[address.data] = tainted_stack.pop(0)

    # Handle CREATE
    elif "CREATE" == instruction.opcode:
        tainted_stack.pop(0)
        tainted_stack.pop(0)
        tainted_stack.pop(0)
        tainted_stack.insert(0, TaintObject(current_stack[0], None))

    # Handle CALL and CALLCODE
    elif "CALL" == instruction.opcode or "CALLCODE" == instruction.opcode:
        tainted_stack.pop(0)
        tainted_stack.pop(0)
        tainted_stack.pop(0)
        in0 = tainted_stack.pop(0).data
        in1 = tainted_stack.pop(0).data
        call_taint = []
        if not isAllReal(in0, in1):
            if in0 in tainted_memory:
                object = tainted_memory[in0]
                if object.taint:
                    for tainted_object in object.taint:
                        call_taint.append(tainted_object)
        else:
            for i in range(in1/32):
                address = in0+i*32
                if address in tainted_memory:
                    object = tainted_memory[address]
                    if object.taint:
                        for tainted_object in object.taint:
                            call_taint.append(tainted_object)
        out0 = tainted_stack.pop(0).data
        out1 = tainted_stack.pop(0).data
        new_var_name = Generator().gen_arbitrary_var()
        new_var = BitVec(new_var_name, 256)
        if not isAllReal(out0, out1):
            if len(call_taint) == 0:
                tainted_memory[out0] = TaintObject(new_var, None)
            else:
                tainted_memory[out0] = TaintObject(new_var, call_taint)
        else:
            for i in range(out1/32):
                address = out0+i*32
                if len(call_taint) == 0:
                    tainted_memory[address] = TaintObject(new_var, None)
                else:
                    tainted_memory[address] = TaintObject(new_var, call_taint)
        if len(call_taint) == 0:
            tainted_stack.insert(0, TaintObject(current_stack[0], None))
        else:
            tainted_stack.insert(0, TaintObject(current_stack[0], call_taint))

    # Handle DELEGATECALL
    elif "DELEGATECALL" == instruction.opcode:
        tainted_stack.pop(0)
        tainted_stack.pop(0)
        in0 = tainted_stack.pop(0).data
        in1 = tainted_stack.pop(0).data
        call_taint = []
        if not isAllReal(in0, in1):
            if in0 in tainted_memory:
                object = tainted_memory[in0]
                if object.taint:
                    for tainted_object in object.taint:
                        call_taint.append(tainted_object)
        else:
            for i in range(in1/32):
                address = in0+i*32
                if address in tainted_memory:
                    object = tainted_memory[address]
                    if object.taint:
                        for tainted_object in object.taint:
                            call_taint.append(tainted_object)
        out0 = tainted_stack.pop(0).data
        out1 = tainted_stack.pop(0).data
        new_var_name = Generator().gen_arbitrary_var()
        new_var = BitVec(new_var_name, 256)
        if not isAllReal(out0, out1):
            if len(call_taint) == 0:
                tainted_memory[out0] = TaintObject(new_var, None)
            else:
                tainted_memory[out0] = TaintObject(new_var, call_taint)
        else:
            for i in range(out1/32):
                address = out0+i*32
                if len(call_taint) == 0:
                    tainted_memory[address] = TaintObject(new_var, None)
                else:
                    tainted_memory[address] = TaintObject(new_var, call_taint)
        if len(call_taint) == 0:
            tainted_stack.insert(0, TaintObject(current_stack[0], None))
        else:
            tainted_stack.insert(0, TaintObject(current_stack[0], call_taint))

    # Hanlde the rest (stack-based opcodes)
    else:
        # IN (pop from stack)
        for i in range(len(instruction.data_in)):
            stack_object = tainted_stack.pop(0)
            if not instruction.opcode in SOURCES:
                if stack_object.taint:
                    if not taint:
                        taint = []
                    for tainted_object in stack_object.taint:
                        if not tainted_object in taint:
                            taint.append(tainted_object)

                if instruction.opcode == "JUMPI":
                    if is_expr(current_block.get_branch_expression()):
                        expression = remove_line_break_space(simplify(current_block.get_branch_expression()))
                        if taint:
                            for tainted_object in taint:
                                for arithmetic_error in arithmetic_errors:
                                    if not tainted_object.__class__.__name__ == "InstructionObject" and tainted_object == arithmetic_error:
                                        for next_block in next_blocks:
                                            next_opcode = (next_block.get_instructions()[-1]).split(' ')[0]
                                            if (next_opcode == "REVERT" or next_opcode == "ASSERTFAIL" or next_opcode == "RETURN" or next_opcode == "JUMP"):
                                                remove = False
                                                # Check for type cast overflow checks
                                                match = re.compile('Not\((.+?) <= 0\)').findall(expression)
                                                if len(match):
                                                    remove = True
                                                # Check if branch expression is simply "True"
                                                match = re.compile('some_condition_(.+?) == 1').findall(expression)
                                                if len(match) == 1 and next_opcode != "JUMP":
                                                    remove = True
                                                # Check for duplicate variables in branch expression
                                                match = []
                                                if len(match) == 0:
                                                    match = re.compile('ULT\((.+?), (.+?)\)').findall(expression)
                                                if len(match) == 0:
                                                    match = re.compile('ULE\((.+?), (.+?)\)').findall(expression)
                                                if len(match) == 0:
                                                    match = re.compile('UGT\((.+?), (.+?)\)').findall(expression)
                                                if len(match) == 0:
                                                    match = re.compile('UGE\((.+?), (.+?)\)').findall(expression)
                                                if len(match) == 0:
                                                    match = re.compile('\((.+?), (.+?)\)').findall(expression)
                                                if len(match) == 1:
                                                    if len(match[0][0]) <= len(match[0][1]):
                                                        if match[0][0] in match[0][1]:
                                                            remove = True
                                                    else:
                                                        if match[0][1] in match[0][0]:
                                                            remove = True
                                                if remove and not arithmetic_error["pc"] in false_positives:
                                                    false_positives.append(arithmetic_error["pc"])

                        # Handle strings
                        matches = re.compile('Extract\(255, 5, 31 \+ (.+?)\)').findall(expression)
                        if len(matches) > 0:
                            remove_taint(matches, taint, tainted_stack, tainted_memory, tainted_storage, arithmetic_errors, false_positives, strings)
                        matches = re.compile('Not\(Extract\(255, 5, (.+?)\) == 0\)').findall(expression)
                        if len(matches) > 0:
                            remove_taint(matches, taint, tainted_stack, tainted_memory, tainted_storage, arithmetic_errors, false_positives, strings)
                        matches = re.compile('Extract\(4, 0, (.+?)\) == 0').findall(expression)
                        if len(matches) > 0:
                            remove_taint(matches, taint, tainted_stack, tainted_memory, tainted_storage, arithmetic_errors, false_positives, strings)
                        matches = re.compile('Not\(ULE\(32, (.+?)\)\)').findall(expression)
                        if len(matches) > 0:
                            remove_taint(matches, taint, tainted_stack, tainted_memory, tainted_storage, arithmetic_errors, false_positives, strings)
                        matches = re.compile('Not\(And\(Extract\(255, .+?, (.+?)\) == 0, ULE\(Extract\(.+?, 0, .+?\), .+?\)\)\)').findall(expression)
                        if len(matches) > 0:
                            remove_taint(matches, taint, tainted_stack, tainted_memory, tainted_storage, arithmetic_errors, false_positives, strings)

                # Remove false positives
                for false_positive in false_positives:
                    for arithmetic_error in arithmetic_errors:
                        if arithmetic_error["pc"] == false_positive:
                            if global_params.DEBUG_MODE:
                                print("================== FALSE POSITIVE =================")
                                print "Removing error from list: "
                                print arithmetic_error
                                print arithmetic_error["instruction"]
                                print("===================================================")
                            arithmetic_errors.remove(arithmetic_error)
        # OUT (insert to stack)
        for i in range(len(instruction.data_out)):
            tainted_stack.insert(i, TaintObject(current_stack[i], taint))
        if global_params.DEBUG_MODE and taint and len(instruction.data_out) > 0:
            print "Propagating taint: "
            for object in taint:
                print " --> "+str(object)

    for arithmetic_error in arithmetic_errors:
        # Strings
        if arithmetic_error["instruction"].opcode == "AND":
            matches = re.compile('256\*If\(Extract\(0, 0, Ia_store_(.+?)\) == 0, 1, 0\)').findall(remove_line_break_space(arithmetic_error["instruction"].data_out[0]))
            if len(matches) > 0:
                if not arithmetic_error["pc"] in false_positives:
                    false_positives.append(arithmetic_error["pc"])
            if remove_line_break_space(arithmetic_error["instruction"].data_in[0]) == "1":
                if not arithmetic_error["pc"] in false_positives:
                    false_positives.append(arithmetic_error["pc"])
        if arithmetic_error["instruction"].opcode == "ADD":
            matches = re.compile('Extract\(255, 5, 31 \+ (.+?)\)').findall(remove_line_break_space(arithmetic_error["instruction"].data_out[0]))
            if len(matches) > 0:
                if not arithmetic_error["pc"] in false_positives:
                    false_positives.append(arithmetic_error["pc"])
            matches = re.compile('32\*Id_(.+?)').findall(remove_line_break_space(arithmetic_error["instruction"].data_in[0]))
            if len(matches) > 0:
                if not arithmetic_error["pc"] in false_positives:
                    false_positives.append(arithmetic_error["pc"])
            matches = re.compile('32\*Id_(.+?)').findall(remove_line_break_space(arithmetic_error["instruction"].data_in[1]))
            if len(matches) > 0:
                if not arithmetic_error["pc"] in false_positives:
                    false_positives.append(arithmetic_error["pc"])
            for sha3 in sha3_list:
                for data in remove_line_break_space(arithmetic_error["instruction"].data_in[0]).split(" "):
                    if remove_line_break_space(sha3) == data and not arithmetic_error["pc"] in false_positives:
                        false_positives.append(arithmetic_error["pc"])
                for data in remove_line_break_space(arithmetic_error["instruction"].data_in[1]).split(" "):
                    if remove_line_break_space(sha3) == data and not arithmetic_error["pc"] in false_positives:
                        false_positives.append(arithmetic_error["pc"])
            if arithmetic_error["instruction"].data_in[0] == 32 or arithmetic_error["instruction"].data_in[0] == 31:
                if not arithmetic_error["pc"] in false_positives:
                    false_positives.append(arithmetic_error["pc"])
            if arithmetic_error["instruction"].data_in[1] == 32 or arithmetic_error["instruction"].data_in[1] == 31:
                if not arithmetic_error["pc"] in false_positives:
                    false_positives.append(arithmetic_error["pc"])
        if arithmetic_error["instruction"].opcode == "MUL":
            if arithmetic_error["instruction"].data_in[0] == 32 or arithmetic_error["instruction"].data_in[1] == 32:
                matches = re.compile('32\*Id_(.+?)').findall(remove_line_break_space(arithmetic_error["instruction"].data_out[0]))
                if len(matches) > 0:
                    if not arithmetic_error["pc"] in false_positives:
                        false_positives.append(arithmetic_error["pc"])
        if arithmetic_error["instruction"].opcode == "SUB":
            matches = re.compile('Extract\(255, 5, 31 \+ (.+?)\)').findall(remove_line_break_space(arithmetic_error["instruction"].data_in[0]))
            if len(matches) > 0:
                if not arithmetic_error["pc"] in false_positives:
                    false_positives.append(arithmetic_error["pc"])
            matches = re.compile('Extract\(255, 5, 31 \+ (.+?)\)').findall(remove_line_break_space(arithmetic_error["instruction"].data_in[1]))
            if len(matches) > 0:
                if not arithmetic_error["pc"] in false_positives:
                    false_positives.append(arithmetic_error["pc"])

def check_taint(tainted_stack, tainted_memory, tainted_storage, instruction, sink_flows, arithmetic_errors, previous_block):
    if instruction.opcode in SINKS:
        if global_params.DEBUG_MODE:
            print "Checking taint: "+str(instruction.opcode)
        validated_errors = []
        if instruction.opcode == "RETURN" or instruction.opcode == "SHA3":
            s0 = tainted_stack[0].data
            s1 = tainted_stack[1].data
            if not isAllReal(s1, s0):
                if s0 in tainted_memory:
                    object = tainted_memory[s0]
                    if object.__class__.__name__ == "TaintObject":
                        if object.taint:
                            sink_flows.append(object.taint)
                            for tainted_object in object.taint:
                                if not tainted_object.__class__.__name__ == "InstructionObject":
                                    if not tainted_object in validated_errors:
                                        validated_errors.append(tainted_object)
            else:
                for i in range(s1/32):
                    address = s0+i*32
                    if address in tainted_memory:
                        object = tainted_memory[address]
                        if object.__class__.__name__ == "TaintObject":
                            if object.taint:
                                sink_flows.append(object.taint)
                                for tainted_object in object.taint:
                                    if not tainted_object.__class__.__name__ == "InstructionObject":
                                        if not tainted_object in validated_errors:
                                            validated_errors.append(tainted_object)
        elif instruction.opcode == "SSTORE" or instruction.opcode == "JUMPI":
            object = tainted_stack[1]
            if object.__class__.__name__ == "TaintObject":
                if object.taint:
                    sink_flows.append(object.taint)
                    for tainted_object in object.taint:
                        if not tainted_object.__class__.__name__ == "InstructionObject":
                            if not tainted_object in validated_errors:
                                validated_errors.append(tainted_object)
        else:
            for i in range(len(instruction.data_in)):
                object = tainted_stack[i]
                if object.__class__.__name__ == "TaintObject":
                    if object.taint:
                        sink_flows.append(object.taint)
                        for tainted_object in object.taint:
                            if not tainted_object.__class__.__name__ == "InstructionObject":
                                if not tainted_object in validated_errors:
                                    validated_errors.append(tainted_object)
        if len(validated_errors) > 0:
            if global_params.DEBUG_MODE:
                print "Validating errors: "

            match = set(re.compile('Concat\(Extract\(255, 160, .+?\), Extract\(255, 96, (.+?)\)\)').findall(remove_line_break_space(tainted_stack[1].data)))
            if len(match) > 0:
                return
            match = set(re.compile('1 \+ 2\*Id_(.+?)').findall(remove_line_break_space(tainted_stack[1].data)))
            if len(match) > 0:
                return
            match = set(re.compile('1 \+ 2\*mem_\[(.+?)\]').findall(remove_line_break_space(tainted_stack[1].data)))
            if len(match) > 0:
                return
            match = set(re.compile('Extract\(255, (.+?), 128 \+ Id_(.+?)\)').findall(remove_line_break_space(tainted_stack[1].data)))
            if len(match) > 0:
                return
            match = set(re.compile('Extract\(255, (.+?), 128 \+ mem_\[(.+?)\]\)').findall(remove_line_break_space(tainted_stack[1].data)))
            if len(match) > 0:
                return

            for validated_error in validated_errors:
                found = False
                for arithmetic_error in arithmetic_errors:
                    if arithmetic_error == validated_error:
                        arithmetic_error["validated"] = True
                        found = True
                if not found:
                    validated_error["validated"] = True
                    arithmetic_errors.append(validated_error)
                if global_params.DEBUG_MODE:
                    print " --> "+str(validated_error)
                """print ""
                print instruction.opcode
                print tainted_stack[0]
                print tainted_stack[1]
                print "validating"
                print " --> "+str(validated_error)
                print validated_error["instruction"]
                print ""
                """

def remove_taint(matches, taint, tainted_stack, tainted_memory, tainted_storage, arithmetic_errors, false_positives, strings):
    if taint:
        for match in matches:
            delete_taint = []
            for tainted_object in taint:
                if tainted_object.__class__.__name__ == "InstructionObject":
                    for data_out in tainted_object.data_out:
                        if str(data_out) == str(match):
                            strings.add(data_out)
                            for data_in in tainted_object.data_in:
                                if is_expr(data_in):
                                    for var in get_vars(data_in):
                                        strings.add(var)
                            if not tainted_object in delete_taint:
                                delete_taint.append(tainted_object)
            # Remove strings from taint
            for tainted_object in delete_taint:
                taint.remove(tainted_object)
        for string in strings:
            # Remove errors caused by strings
            for arithmetic_error in arithmetic_errors:
                for data_in in arithmetic_error["instruction"].data_in:
                    if is_expr(data_in):
                        if string in get_vars(data_in):
                            if not arithmetic_error["pc"] in false_positives:
                                false_positives.append(arithmetic_error["pc"])
            # Remove strings from tainted stack
            for tainted_stack_object in tainted_stack:
                if tainted_stack_object.taint:
                    delete_taint = []
                    for tainted_object in tainted_stack_object.taint:
                        if tainted_object.__class__.__name__ == "InstructionObject":
                            for data_out in tainted_object.data_out:
                                if is_expr(data_out):
                                    if string in get_vars(data_out):
                                        if not tainted_object in delete_taint:
                                            delete_taint.append(tainted_object)
                        elif tainted_object in false_positives:
                            if not tainted_object in delete_taint:
                                delete_taint.append(tainted_object)
                    for tainted_object in delete_taint:
                        tainted_stack_object.taint.remove(tainted_object)
                    if len(tainted_stack_object.taint) == 0:
                        tainted_stack_object.taint = None
            # Remove strings from tainted memory
            for address in tainted_memory:
                if tainted_memory[address].taint:
                    delete_taint = []
                    for tainted_object in tainted_memory[address].taint:
                        if tainted_object.__class__.__name__ == "InstructionObject":
                            for data_out in tainted_object.data_out:
                                if is_expr(data_out):
                                    if string in get_vars(data_out):
                                        if not tainted_object in delete_taint:
                                            delete_taint.append(tainted_object)
                        elif tainted_object in false_positives:
                            if not tainted_object in delete_taint:
                                delete_taint.append(tainted_object)
                    for tainted_object in delete_taint:
                        tainted_memory[address].taint.remove(tainted_object)
                    if len(tainted_memory[address].taint) == 0:
                        tainted_memory[address].taint = None
            # Remove strings from tainted storage
            for address in tainted_storage:
                if tainted_storage[address].taint:
                    delete_taint = []
                    for tainted_object in tainted_storage[address].taint:
                        if tainted_object.__class__.__name__ == "InstructionObject":
                            for data_out in tainted_object.data_out:
                                if is_expr(data_out):
                                    if string in get_vars(data_out):
                                        if not tainted_object in delete_taint:
                                            delete_taint.append(tainted_object)
                        elif tainted_object in false_positives:
                            if not tainted_object in delete_taint:
                                delete_taint.append(tainted_object)
                    for tainted_object in delete_taint:
                        tainted_storage[address].taint.remove(tainted_object)
                    if len(tainted_storage[address].taint) == 0:
                        tainted_storage[address].taint = None

def perform_taint_analysis(previous_block, current_block, next_blocks, pc, opcode, previous_stack, current_stack, arithmetic_errors):
    global branches
    global tainted_stack
    global tainted_memory
    global tainted_storage
    global storage_flows
    global sink_flows
    global sha3_list
    global false_positives
    global strings

    try:
        # Get number of items taken/added to stack by this opcode
        items_taken_count = get_opcode(opcode)[1]
        items_added_count = get_opcode(opcode)[2]

        # IN: arguments pop'ed from (previous) stack
        data_in = []
        for i in range(items_taken_count):
            data_in.append(previous_stack[i])

        # OUT: values written to (new) stack
        data_out = []
        for i in range(items_added_count):
            data_out.append(current_stack[i])

        # Create an instruction object
        instruction = InstructionObject(opcode, data_in, data_out)

        # Load tainted stack, memory and storage if we are at a branch
        if pc in branches and previous_block.get_end_address() in branches[pc]:
            tainted_stack = branches[pc][previous_block.get_end_address()]["tainted_stack"][:]
            tainted_memory = copy.deepcopy(branches[pc][previous_block.get_end_address()]["tainted_memory"])
            tainted_storage = copy.deepcopy(branches[pc][previous_block.get_end_address()]["tainted_storage"])

        #################### TAINT LOGIC ###################
        # Introduce taint
        taint = introduce_taint(instruction, pc, arithmetic_errors)
        # Check taint
        check_taint(tainted_stack, tainted_memory, tainted_storage, instruction, sink_flows, arithmetic_errors, previous_block)
        # Propagate taint
        propagate_taint(taint, tainted_stack, tainted_memory, tainted_storage, instruction, current_stack, previous_block, current_block, next_blocks, arithmetic_errors, sha3_list, false_positives, strings)
        ####################################################

        if pc == current_block.get_end_address():
            if current_block.get_block_type() == "conditional":
                left_branch = previous_stack[0]
                right_branch = pc+1
                # Preserve the current tainted stack, memory and storage to the left branch
                if not left_branch in branches:
                    branches[left_branch] = {}
                branches[left_branch][pc] = {}
                branches[left_branch][pc]["tainted_stack"] = tainted_stack[:]
                branches[left_branch][pc]["tainted_memory"] = copy.deepcopy(tainted_memory)
                branches[left_branch][pc]["tainted_storage"] = copy.deepcopy(tainted_storage)
                # Preserve the current tainted stack, memory and storage to the right branch
                if not right_branch in branches:
                    branches[right_branch] = {}
                branches[right_branch][pc] = {}
                branches[right_branch][pc]["tainted_stack"] = tainted_stack[:]
                branches[right_branch][pc]["tainted_memory"] = copy.deepcopy(tainted_memory)
                branches[right_branch][pc]["tainted_storage"] = copy.deepcopy(tainted_storage)
            elif current_block.get_block_type() == "terminal":
                ##### INTRAPROCEDURAL TAINT ANALYSIS #####
                if global_params.INTERPROCEDURAL_TAINT:
                    if len(tainted_storage) > 0:
                        storage_flows.append(copy.deepcopy(tainted_storage))
                    for sink_flow in sink_flows:
                        storage_addresses = []
                        errors_found = []
                        for tainted_object in sink_flow:
                            if tainted_object.__class__.__name__ == "InstructionObject":
                                if tainted_object.opcode == "SLOAD":
                                    storage_addresses.append(tainted_object.data_in[0])
                            else:
                                for arithmetic_error in arithmetic_errors:
                                    if tainted_object == arithmetic_error:
                                        errors_found.append(tainted_object)
                        if len(storage_addresses) > 0 and len(errors_found) > 0:
                            for storage in storage_flows:
                                for address in storage_addresses:
                                    if address in storage and storage[address].taint:
                                        for tainted_object in storage[address].taint:
                                            if tainted_object.__class__.__name__ == "InstructionObject" and tainted_object.opcode in SOURCES:
                                                for arithmetic_error in arithmetic_errors:
                                                    if arithmetic_error in errors_found:
                                                        arithmetic_error["validated"] = True

    except:
        traceback.print_exc()
        print "Unexpected error:", sys.exc_info()[0]

def is_input_tainted(instruction):
    if instruction.opcode == "ADD" or instruction.opcode == "MUL" or instruction.opcode == "SUB" or instruction.opcode == "SDIV" or instruction.opcode == "AND" or instruction.opcode == "SIGNEXTEND":
        if not (tainted_stack[0].taint == None and tainted_stack[1].taint == None):
            return True

    if instruction.opcode == "DIV" or instruction.opcode == "MOD" or instruction.opcode == "SMOD":
        if not tainted_stack[1].taint == None:
            return True

    if instruction.opcode == "ADDMOD" or instruction.opcode == "MULMOD":
        if not tainted_stack[2].taint == None:
            return True

    return False
