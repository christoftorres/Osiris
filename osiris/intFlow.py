import re
import global_params
import traceback

from utils import *
from z3 import *

def enum(**named_values):
    return type('Enum', (), named_values)

ErrorTypes = enum(OVERFLOW='Overflow', UNDERFLOW='Underflow', SIGNEDNESS='Signedness', DIVISION='Division', MODULO='Modulo', WIDTH_CONVERSION='Width conversion')

IntegerTypes = enum(TOP='Top', SIGNED='Signed', UNSIGNED='Unsigned', BOTTOM='Bottom')

conversions = []

def get_int_size(x):
    return x + 2 if is_int_signed(x) else x + 1

def is_int_signed(x):
    return (x % 2 == 0)

def initialize_var(var, type_information):
    type_information[var] = IntegerTypes.TOP

def check_signedness_conversion(expression, type_information, sign_extension, signed_operation, instruction, path_conditions, arithmetic_errors, arithmetic_models, pc):
    signedness_conversion = False
    if is_expr(expression):
        for var in type_information:
            if var in get_vars(expression):
                if signed_operation and not sign_extension and type_information[var] == IntegerTypes.TOP and not instruction.opcode in ['SDIV', 'SMOD']:
                    type_information[var] = IntegerTypes.UNSIGNED
                # Unsigned operation
                if not signed_operation:
                    if (type_information[var] == IntegerTypes.SIGNED):
                        type_information[var] = IntegerTypes.BOTTOM
                        signedness_conversion = True
                    else:
                        type_information[var] = IntegerTypes.UNSIGNED
                # Signed operation
                else:
                    if (type_information[var] == IntegerTypes.UNSIGNED):
                        type_information[var] = IntegerTypes.BOTTOM
                        signedness_conversion = True
                    else:
                        type_information[var] = IntegerTypes.SIGNED
    if signedness_conversion:
        s = Solver()
        s.set("timeout", global_params.ARITHMETIC_TIMEOUT)
        s.add(path_conditions)
        arithmetic_error = {}
        arithmetic_error["instruction"] = instruction
        arithmetic_error["validated"]   = False
        arithmetic_error["type"]        = ErrorTypes.SIGNEDNESS
        arithmetic_error["pc"]          = pc
        if global_params.MODEL_INPUT:
            if not pc in arithmetic_models:
                arithmetic_models[pc] = s.model()
        arithmetic_errors.append(arithmetic_error)
        if global_params.DEBUG_MODE:
            print("===================================================")
            print("!!!SIGNEDNESS CONVERSION!!!")
            print("===================================================")
        return True
    else:
        if global_params.DEBUG_MODE:
            print("===================================================")
            print("!!!NO SIGNEDNESS CONVERSION!!!")
            print("===================================================")
        return False

def check_width_conversion(first, second, target, instruction, current_block, path_conditions, arithmetic_errors, arithmetic_models, pc):
    source = None
    truncator = None

    if isSymbolic(first) and isReal(second):
        source    = first
        truncator = second
    else:
        source    = second
        truncator = first

    if instruction:
        for conversion in conversions:
            if remove_line_break_space(conversion["target"]) in remove_line_break_space(source) and instruction.opcode == conversion["opcode"]:
                false_positives = []
                for arithmetic_error in arithmetic_errors:
                    if arithmetic_error["instruction"].data_out[0] == conversion["target"]:
                        if not arithmetic_error in false_positives:
                            false_positives.append(arithmetic_error)
                for false_positive in false_positives:
                    arithmetic_errors.remove(false_positive)

    if truncator == int("ffffffffffffffffffffffffffffffffffffffff", 16):
        return False

    if truncator.__class__.__name__ == "BitVecNumRef":
        truncator = truncator.as_long()

    if isReal(truncator):
        binary = "{0:b}".format(truncator)
        for i in range(len(binary)):
            if binary[i] == '0':
                return False
        if instruction.opcode == "AND" and is_expr(source):
            if truncator == 255 and len(get_vars(source)) == 1 and "Ia_store_" in str(get_vars(source)[0]):
                return False

    if is_expr(source) and current_block:
        if len(get_vars(source)) == 1 and "Id_" in str(get_vars(source)[0]) and str(get_vars(source)[0]) == str(source) and "CALLDATALOAD " in current_block.get_instructions():
            return False

    s = Solver()
    s.set("timeout", global_params.ARITHMETIC_TIMEOUT)
    if path_conditions:
        s.add(path_conditions)
    s.add(source > target)
    try:
        if s.check() == sat:
            if instruction:
                arithmetic_error = {}
                arithmetic_error["instruction"] = instruction
                arithmetic_error["validated"]   = False
                arithmetic_error["type"]        = ErrorTypes.WIDTH_CONVERSION
                arithmetic_error["pc"]          = pc
                if global_params.MODEL_INPUT:
                    if not pc in arithmetic_models:
                        arithmetic_models[pc] = s.model()
                arithmetic_errors.append(arithmetic_error)
                conversion = {}
                conversion["target"] = target
                conversion["opcode"] = instruction.opcode
                if not conversion in conversions:
                    conversions.append(conversion)
                if global_params.DEBUG_MODE:
                    print("===================================================")
                    print("!!!WIDTH CONVERSION!!!")
                    print("===================================================")
            return True
        else:
            if instruction:
                if global_params.DEBUG_MODE:
                    print("===================================================")
                    print("!!!NO WIDTH CONVERSION!!!")
                    print("===================================================")
            return False
    except:
        traceback.print_exc
        pass
    return False

def addition_overflow_check(augend, addend, analysis, instruction, path_conditions, arithmetic_errors, arithmetic_models, pc):
    if augend == 0 or addend == 0:
        return False

    if global_params.DEBUG_MODE:
        print("===================================================")

    # Infer information from the augend
    augend_size = 256
    augend_sign = False
    try:
        if isReal(augend):
            augend = BitVecVal(augend, 256)
        else:
            match = re.compile('Extract\((.+?), 0, .+?\)').findall(remove_line_break_space(augend))
            if len(match) > 0:
                augend_value = max([int(value) for value in match])
                augend_size = get_int_size(augend_value)
                augend_sign = is_int_signed(augend_value)
    except:
        pass
    if global_params.DEBUG_MODE:
        print("---> augend ("+str(augend_size)+"): "+str(augend))

    # Infer information from the addend
    addend_size = 256
    addend_sign = False
    try:
        if isReal(addend):
            addend = BitVecVal(addend, 256)
        else:
            match = re.compile('Extract\((.+?), 0, .+?\)').findall(remove_line_break_space(addend))
            if len(match) > 0:
                addend_value = max([int(value) for value in match])
                addend_size = get_int_size(addend_value)
                addend_sign = is_int_signed(addend_value)
    except:
        pass
    if global_params.DEBUG_MODE:
        print("---> addend ("+str(addend_size)+"): "+str(addend))

    # Infer the size of the larger operand
    if augend_size == 256 or addend_size == 256:
        if isReal(augend) or augend.__class__.__name__ == "BitVecNumRef" or isReal(addend) or addend.__class__.__name__ == "BitVecNumRef":
            max_size = max(augend_size, addend_size)
        else:
            max_size = min(augend_size, addend_size)
    else:
        max_size = max(augend_size, addend_size)
    if global_params.DEBUG_MODE:
        if augend_sign == False and addend_sign == False:
            print("max_size: "+str(max_size))+" (unsigned)"
        else:
            print("max_size: "+str(max_size))+" (signed)"

    # Prepare the solver
    s = Solver()
    s.set("timeout", global_params.ARITHMETIC_TIMEOUT)

    # Remove certain path conditions if a reentrancy_bug is detected
    if True in analysis["reentrancy_bug"]:
        for path_condition in path_conditions:
            if not (str(augend) in str(get_vars(path_condition)) and str(addend) in str(get_vars(path_condition))):
                s.add(path_condition)
    else:
        s.add(path_conditions)

    # Add contraint for unsigned addition overflow checking
    if augend_sign == False and addend_sign == False:
        if max_size == 256:
            s.add(Not(bvadd_no_overflow(augend, addend)))
        else:
            s.add(augend + addend > 2**max_size - 1)
    # Add contraint for signed addition overflow checking
    else:
        if max_size == 256:
            s.add(Not(bvadd_no_overflow(augend, addend, True)))
        else:
            s.add(augend + addend > 2**(max_size - 1) - 1)

    # Check on the satisfiability of the current formula
    try:
        if s.check() == sat:
            arithmetic_error = {}
            arithmetic_error["instruction"] = instruction
            arithmetic_error["validated"]   = False
            arithmetic_error["type"]        = ErrorTypes.OVERFLOW
            arithmetic_error["pc"]          = pc
            if global_params.MODEL_INPUT:
                if not pc in arithmetic_models:
                    arithmetic_models[pc] = s.model()
            arithmetic_errors.append(arithmetic_error)
            if global_params.DEBUG_MODE:
                print("!!!OVERFLOW!!!")
                print("===================================================")
            return True
        else:
            pass
            if global_params.DEBUG_MODE:
                print("!!!NO OVERFLOW!!!")
                print("===================================================")
            return False
    except:
        pass
    return False

def multiplication_overflow_check(multiplier, multiplicand, analysis, instruction, path_conditions, arithmetic_errors, arithmetic_models, pc):
    if multiplier == 1 or multiplicand == 1:
        return False

    if multiplier == 0 or multiplicand == 0:
        return False

    if global_params.DEBUG_MODE:
        print("===================================================")

    # Infer information from the multiplier
    multiplier_size = 256
    multiplier_sign = False
    try:
        if isReal(multiplier):
            multiplier = BitVecVal(multiplier, 256)
        else:
            match = re.compile('Extract\((.+?), 0, .+?\)').findall(remove_line_break_space(multiplier))
            if len(match) > 0:
                multiplier_value = max([int(value) for value in match])
                multiplier_size = get_int_size(multiplier_value)
                multiplier_sign = is_int_signed(multiplier_value)
    except:
        pass
    if global_params.DEBUG_MODE:
        print("---> multiplier ("+str(multiplier_size)+"): "+str(multiplier))

    # Infer information from the multiplicand
    multiplicand_size = 256
    multiplicand_sign = False
    try:
        if isReal(multiplicand):
            multiplicand = BitVecVal(multiplicand, 256)
        else:
            match = re.compile('Extract\((.+?), 0, .+?\)').findall(remove_line_break_space(multiplicand))
            if len(match) > 0:
                multiplicand_value = max([int(value) for value in match])
                multiplicand_size = get_int_size(multiplicand_value)
                multiplicand_sign = is_int_signed(multiplicand_value)
    except:
        pass
    if global_params.DEBUG_MODE:
        print("---> multiplicand ("+str(multiplicand_size)+"): "+str(multiplicand))

    # Infer the size of the larger operand
    if multiplier_size == 256 or multiplicand_size == 256:
        if isReal(multiplier) or multiplier.__class__.__name__ == "BitVecNumRef" or isReal(multiplicand) or multiplicand.__class__.__name__ == "BitVecNumRef":
            max_size = max(multiplier_size, multiplicand_size)
        else:
            max_size = min(multiplier_size, multiplicand_size)
    else:
        max_size = max(multiplier_size, multiplicand_size)
    if global_params.DEBUG_MODE:
        if multiplier_sign == False and multiplicand_sign == False:
            print("max_size: "+str(max_size))+" (unsigned)"
        else:
            print("max_size: "+str(max_size))+" (signed)"

    # Prepare the solver
    s = Solver()
    s.set("timeout", global_params.ARITHMETIC_TIMEOUT)

    # Remove certain path conditions if a reentrancy_bug is detected
    if True in analysis["reentrancy_bug"]:
        for path_condition in path_conditions:
            if not (str(multiplier) in str(get_vars(path_condition)) and str(multiplicand) in str(get_vars(path_condition))):
                s.add(path_condition)
    else:
        s.add(path_conditions)

    # Add contraint for unsigned multiplication overflow checking
    if multiplier_sign == False and multiplicand_sign == False:
        if max_size == 256:
            if multiplier.__class__.__name__ == "BitVecRef" and multiplicand.__class__.__name__ == "BitVecRef":
                s.add(Not(bvmul_no_overflow(multiplier, multiplicand)))
            else:
                if multiplier.__class__.__name__ == "BitVecNumRef" and multiplicand.__class__.__name__ == "BitVecNumRef":
                    multiplier   = multiplier.as_long()
                    multiplicand = multiplicand.as_long()
                s.add(Not(bvmul_no_overflow(multiplier, multiplicand)))
        else:
            s.add(multiplier * multiplicand > 2**max_size - 1)
    # Add contraint for signed multiplication overflow checking
    else:
        if max_size == 256:
            s.add(Not(bvmul_no_overflow(multiplier, multiplicand, True)))
        else:
            s.add(multiplier * multiplicand > 2**(max_size - 1) - 1)

    # Check on the satisfiability of the current formula
    try:
        if s.check() == sat:
            arithmetic_error = {}
            arithmetic_error["instruction"] = instruction
            arithmetic_error["validated"]   = False
            arithmetic_error["type"]        = ErrorTypes.OVERFLOW
            arithmetic_error["pc"]          = pc
            if global_params.MODEL_INPUT:
                if not pc in arithmetic_models:
                    arithmetic_models[pc] = s.model()
            arithmetic_errors.append(arithmetic_error)
            if global_params.DEBUG_MODE:
                print("!!!OVERFLOW!!!")
                print("===================================================")
            return True
        else:
            if global_params.DEBUG_MODE:
                print("!!!NO OVERFLOW!!!")
                print("===================================================")
            return False
    except Exception as e:
        print e
        traceback.print_exc()
        pass
    return False

def subtraction_underflow_check(minuend, subtrahend, analysis, instruction, path_conditions, arithmetic_errors, arithmetic_models, pc):
    if subtrahend == 0:
        return False

    if global_params.DEBUG_MODE:
        print("===================================================")

    # Infer information from the minuend
    minuend_size = 256
    minuend_sign = False
    try:
        if isReal(minuend):
            minuend = BitVecVal(minuend, 256)
        else:
            match = re.compile('Extract\((.+?), 0, .+?\)').findall(remove_line_break_space(minuend))
            if len(match) > 0:
                minuend_value = max([int(value) for value in match])
                minuend_size = get_int_size(minuend_value)
                minuend_sign = is_int_signed(minuend_value)
    except:
        pass
    if global_params.DEBUG_MODE:
        print("---> minuend ("+str(minuend_size)+"): "+str(minuend))

    # Infer information from the subtrahend
    subtrahend_size = 256
    subtrahend_sign = False
    try:
        if isReal(subtrahend):
            subtrahend = BitVecVal(subtrahend, 256)
        else:
            match = re.compile('Extract\((.+?), 0, .+?\)').findall(remove_line_break_space(subtrahend))
            if len(match) > 0:
                subtrahend_value = max([int(value) for value in match])
                subtrahend_size = get_int_size(subtrahend_value)
                subtrahend_sign = is_int_signed(subtrahend_value)
    except:
        pass
    if global_params.DEBUG_MODE:
        print("---> subtrahend ("+str(subtrahend_size)+"): "+str(subtrahend))

    # Infer the size of the larger operand
    if minuend_size == 256 or subtrahend_size == 256:
        if isReal(minuend) or minuend.__class__.__name__ == "BitVecNumRef" or isReal(subtrahend) or subtrahend.__class__.__name__ == "BitVecNumRef":
            max_size = max(minuend_size, subtrahend_size)
        else:
            max_size = min(minuend_size, subtrahend_size)
    else:
        max_size = max(minuend_size, subtrahend_size)
    if global_params.DEBUG_MODE:
        if minuend_sign == False and subtrahend_sign == False:
            print("max_size: "+str(max_size))+" (unsigned)"
        else:
            print("max_size: "+str(max_size))+" (signed)"

    # Prepare the solver
    s = Solver()
    s.set("timeout", global_params.ARITHMETIC_TIMEOUT)

    # Remove certain path conditions if a reentrancy_bug is detected
    if True in analysis["reentrancy_bug"]:
        for path_condition in path_conditions:
            if not (str(minuend) in str(get_vars(path_condition)) and str(subtrahend) in str(get_vars(path_condition))):
                s.add(path_condition)
    else:
        s.add(path_conditions)

    # Add contraint for unsigned subtraction overflow checking
    if minuend_sign == False and subtrahend_sign == False:
        if max_size == 256:
            if simplify(minuend - subtrahend).__class__.__name__ == "BitVecNumRef":
                    s.add(simplify(minuend - subtrahend) < 0)
            else:
                s.add(Not(bvsub_no_underflow(minuend, subtrahend)))
        else:
            s.add(minuend - subtrahend < 0)
    # Add contraint for signed subtraction overflow checking
    else:
        if max_size == 256:
            s.add(Not(bvsub_no_underflow(minuend, subtrahend, True)))
        else:
            s.add(And(minuend - subtrahend < 0, UGE(minuend - subtrahend, 2**(max_size-1))))
    # Check on the satisfiability of the current formula
    try:
        if s.check() == sat:
            arithmetic_error = {}
            arithmetic_error["instruction"] = instruction
            arithmetic_error["validated"]   = False
            arithmetic_error["type"]        = ErrorTypes.UNDERFLOW
            arithmetic_error["pc"]          = pc
            if global_params.MODEL_INPUT:
                if not pc in arithmetic_models:
                    arithmetic_models[pc] = s.model()
            arithmetic_errors.append(arithmetic_error)
            if global_params.DEBUG_MODE:
                print("!!!UNDERFLOW!!!")
                print("===================================================")
            return True
        else:
            if global_params.DEBUG_MODE:
                print("!!!NO UNDERFLOW!!!")
                print("===================================================")
            return False
    except:
        pass
    return False

def unsigned_division_check(divisor, instruction, path_conditions, arithmetic_errors, arithmetic_models, pc):
    if global_params.DEBUG_MODE:
        print("===================================================")
        print("---> divisor: "+str(divisor))
    # Prepare the solver
    s = Solver()
    s.set("timeout", global_params.ARITHMETIC_TIMEOUT)
    s.add(path_conditions)
    # Add contraint for division by zero checking
    if divisor.__class__.__name__ == "BitVecNumRef":
        divisor = divisor.as_long()
    s.add(divisor == 0)
    # Check on the satisfiability of the current formula
    try:
        if s.check() == sat:
            arithmetic_error = {}
            arithmetic_error["instruction"] = instruction
            arithmetic_error["validated"]   = False
            arithmetic_error["type"]        = ErrorTypes.DIVISION
            arithmetic_error["pc"]          = pc
            if global_params.MODEL_INPUT:
                if not pc in arithmetic_models:
                    arithmetic_models[pc] = s.model()
            arithmetic_errors.append(arithmetic_error)
            if global_params.DEBUG_MODE:
                print("!!!DIVISION BY ZERO POSSIBLE!!!")
                print("===================================================")
            return True
        else:
            if global_params.DEBUG_MODE:
                print("!!!NO DIVISION BY ZERO POSSIBLE!!!")
                print("===================================================")
            return False
    except:
        pass
    return False

def signed_division_check(dividend, divisor, instruction, path_conditions, arithmetic_errors, arithmetic_models, pc):
    if global_params.DEBUG_MODE:
        print("===================================================")
        print("---> dividend: "+str(dividend))
        print("---> divisor: "+str(divisor))
    # Prepare the solver
    s = Solver()
    s.set("timeout", global_params.ARITHMETIC_TIMEOUT)
    s.add(path_conditions)
    s.push()
    # Add contraint for division by zero checking
    if divisor.__class__.__name__ == "BitVecNumRef":
        divisor = divisor.as_long()
    s.add(divisor == 0)
    # Check on the satisfiability of the current formula
    try:
        if s.check() == sat:
            arithmetic_error = {}
            arithmetic_error["instruction"] = instruction
            arithmetic_error["validated"]   = False
            arithmetic_error["type"]        = ErrorTypes.DIVISION
            arithmetic_error["pc"]          = pc
            if global_params.MODEL_INPUT:
                if not pc in arithmetic_models:
                    arithmetic_models[pc] = s.model()
            arithmetic_errors.append(arithmetic_error)
            if global_params.DEBUG_MODE:
                print("!!!DIVISION BY ZERO POSSIBLE!!!")
                print("===================================================")
            return True
        else:
            if global_params.DEBUG_MODE:
                print("!!!NO DIVISION BY ZERO POSSIBLE!!!")
                print("===================================================")
    except:
        pass
    s.pop()
    s.push()
    # Add contraint for signed division checking
    if dividend.__class__.__name__ == "BitVecNumRef":
        dividend = dividend.as_long()
    s.add(And(dividend == -2**255, divisor == -1 ))
    # Check on the satisfiability of the current formula
    try:
        if s.check() == sat:
            arithmetic_error = {}
            arithmetic_error["instruction"] = instruction
            arithmetic_error["validated"]   = False
            arithmetic_error["type"]        = ErrorTypes.DIVISION
            arithmetic_error["pc"]          = pc
            if global_params.MODEL_INPUT:
                if not pc in arithmetic_models:
                    arithmetic_models[pc] = s.model()
            arithmetic_errors.append(arithmetic_error)
            if global_params.DEBUG_MODE:
                print("!!!SIGNED DIVISION IS NOT IN BOUNDS!!!")
                print("===================================================")
            return True
        else:
            if global_params.DEBUG_MODE:
                print("!!!SIGNED DIVISION IS IN BOUNDS!!!")
                print("===================================================")
            return False
    except:
        pass
    s.pop()
    return False

def modulo_check(modulus, instruction, path_conditions, arithmetic_errors, arithmetic_models, pc):
    if global_params.DEBUG_MODE:
        print("===================================================")
        print("---> modulus: "+str(modulus))
    # Prepare the solver
    s = Solver()
    s.set("timeout", global_params.ARITHMETIC_TIMEOUT)
    s.add(path_conditions)
    # Add contraint for modulus by zero checking
    if modulus.__class__.__name__ == "BitVecNumRef":
        modulus = modulus.as_long()
    s.add(modulus == 0)
    # Check on the satisfiability of the current formula
    try:
        if s.check() == sat:
            arithmetic_error = {}
            arithmetic_error["instruction"] = instruction
            arithmetic_error["validated"]   = False
            arithmetic_error["type"]        = ErrorTypes.MODULO
            arithmetic_error["pc"]          = pc
            if global_params.MODEL_INPUT:
                if not pc in arithmetic_models:
                    arithmetic_models[pc] = s.model()
            arithmetic_errors.append(arithmetic_error)
            if global_params.DEBUG_MODE:
                print("!!!ZERO MODULUS POSSIBLE!!!")
                print("===================================================")
            return True
        else:
            if global_params.DEBUG_MODE:
                print("!!!NO ZERO MODULUS POSSIBLE!!!")
                print("===================================================")
            return False
    except:
        pass
    return False

#################################
# Watch for BitVector Overflows #
#################################

def bvadd_no_overflow(x, y, signed=False):
    assert x.ctx_ref()==y.ctx_ref()
    a, b = z3._coerce_exprs(x, y)
    return BoolRef(Z3_mk_bvadd_no_overflow(a.ctx_ref(), a.as_ast(), b.as_ast(), signed))

def bvmul_no_overflow(x, y, signed=False):
    assert x.ctx_ref()==y.ctx_ref()
    a, b = z3._coerce_exprs(x, y)
    return BoolRef(Z3_mk_bvmul_no_overflow(a.ctx_ref(), a.as_ast(), b.as_ast(), signed))

def bvsub_no_underflow(x, y, signed=False):
    assert x.ctx_ref()==y.ctx_ref()
    a, b = z3._coerce_exprs(x, y)
    return BoolRef(Z3_mk_bvsub_no_underflow(a.ctx_ref(), a.as_ast(), b.as_ast(), signed))
