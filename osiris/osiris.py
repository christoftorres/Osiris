#!/usr/bin/env python

import shlex
import subprocess
import os
import re
import argparse
import logging
import requests
import symExec
import global_params
import z3
import z3.z3util

from source_map import SourceMap
from utils import run_command
from HTMLParser import HTMLParser

def cmd_exists(cmd):
    '''
    Runs cmd in a process and returns true if exit code is 0.
    '''
    return subprocess.call(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0

def has_dependencies_installed():
    '''
    Returns true if dependencies to Z3, evm, and solc are satisfied, else returns false.
    '''
    try:
        if z3.get_version_string() != '4.6.0':
            logging.warning("You are using z3 version %s. The supported version is 4.6.0." % z3.get_version_string())
    except:
        logging.critical("Z3 is not available. Please install z3 from https://github.com/Z3Prover/z3.")
        return False

    if not cmd_exists("evm"):
        logging.critical("Please install evm from go-ethereum and make sure it is in the path.")
        return False
    else:
        cmd = "evm --version"
        out = run_command(cmd).strip()
        version = re.findall(r"evm version (\d*.\d*.\d*)", out)[0]
        if version != '1.8.3':
            logging.warning("You are using evm version %s. The supported version is 1.8.3." % version)

    if not cmd_exists("solc --version"):
        logging.critical("solc is missing. Please install the solidity compiler and make sure solc is in the path.")
        return False
    else:
        cmd = "solc --version"
        out = run_command(cmd).strip()
        version = re.findall(r"Version: (\d*.\d*.\d*)", out)[0]
        if version != '0.4.21':
            logging.warning("You are using solc version %s. The supported version is 0.4.21." % version)

    return True

def removeSwarmHash(evm):
    '''
    TODO Purpose?
    '''
    evm_without_hash = re.sub(r"a165627a7a72305820\S{64}0029$", "", evm)
    return evm_without_hash

def extract_bin_str(s):
    '''
    Extracts binary representation of smart contract from solc output.
    '''
    binary_regex = r"\r?\n======= (.*?) =======\r?\nBinary of the runtime part: \r?\n(.*?)\r?\n"
    contracts = re.findall(binary_regex, s)
    contracts = [contract for contract in contracts if contract[1]]
    if not contracts:
        logging.critical("Solidity compilation failed")
        print "======= error ======="
        print "Solidity compilation failed"
        exit()
    return contracts

def compileContracts(contract):
    '''
    Calls solc --bin-runtime to compile contract and returns binary representation of contract.
    '''
    cmd = "solc --bin-runtime %s" % contract
    out = run_command(cmd)

    libs = re.findall(r"_+(.*?)_+", out)
    libs = set(libs)
    if libs:
        return link_libraries(contract, libs)
    else:
        return extract_bin_str(out)


def link_libraries(filename, libs):
    '''
    Compiles contract in filename and links libs by calling solc --link. Returns binary representation of linked contract.
    '''
    option = ""
    for idx, lib in enumerate(libs):
        lib_address = "0x" + hex(idx+1)[2:].zfill(40)
        option += " --libraries %s:%s" % (lib, lib_address)
    FNULL = open(os.devnull, 'w')
    cmd = "solc --bin-runtime %s" % filename
    p1 = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=FNULL)
    cmd = "solc --link%s" %option
    p2 = subprocess.Popen(shlex.split(cmd), stdin=p1.stdout, stdout=subprocess.PIPE, stderr=FNULL)
    p1.stdout.close()
    out = p2.communicate()[0]
    return extract_bin_str(out)

def analyze(processed_evm_file, disasm_file, source_map = None):
    '''Runs the symbolic execution.

        Parameters
    ----------
    processed_evm_file : File descriptor of EVM bytecode file on which "removeSwarmHash" has been removed  TODO: Why not remove this argument and process disasm_file as necessary within analyze()? This way, the function makes implicit assumptions about the relation between those two arguments.
    disasm_file: File descriptor of the original EVM asm file
    source_map: SourceMap of compiled contracts
    '''
    disasm_out = ""

    # Check if processed_evm_file can be disassembled
    # TODO: Why this check? The result is not used anyway and it is not said that processed_evm_file is related to disasm_file.
    try:
        disasm_p = subprocess.Popen(
            ["evm", "disasm", processed_evm_file], stdout=subprocess.PIPE)
        disasm_out = disasm_p.communicate()[0]
    except:
        logging.critical("Disassembly failed.")
        exit()

    with open(disasm_file, 'w') as of:
        of.write(disasm_out)

    # Run symExec
    if source_map is not None:
        symExec.main(disasm_file, args.source, source_map)
    else:
        symExec.main(disasm_file, args.source)

def remove_temporary_file(path):
    '''Does what it says (no matter if the file was temporary).
    '''
    if os.path.isfile(path):
        try:
            os.unlink(path)
        except:
            pass

def main():
    global args

    print("")
    print("  .oooooo.             o8o            o8o          ")
    print(" d8P'  `Y8b            `\"'            `\"'          ")
    print("888      888  .oooo.o oooo  oooo d8b oooo   .oooo.o")
    print("888      888 d88(  \"8 `888  `888\"\"8P `888  d88(  \"8")
    print("888      888 `\"Y88b.   888   888      888  `\"Y88b. ")
    print("`88b    d88' o.  )88b  888   888      888  o.  )88b")
    print(" `Y8bood8P'  8\"\"888P' o888o d888b    o888o 8\"\"888P'")
    print("")

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-s", "--source", type=str,
                       help="local source file name. Solidity by default. Use -b to process evm instead. Use stdin to read from stdin.")
    group.add_argument("-ru", "--remoteURL", type=str,
                       help="Get contract from remote URL. Solidity by default. Use -b to process evm instead.", dest="remote_URL")

    parser.add_argument("--version", action="version", version="Osiris version 0.0.1 - 'Memphis' (Oyente version 0.2.7 - Commonwealth)")
    parser.add_argument(
        "-b", "--bytecode", help="read bytecode in source instead of solidity file.", action="store_true")

    parser.add_argument(
        "-j", "--json", help="Redirect results to a json file.", action="store_true")
    parser.add_argument(
        "-e", "--evm", help="Do not remove the .evm file.", action="store_true")
    parser.add_argument(
        "-p", "--paths", help="Print path condition information.", action="store_true")
    parser.add_argument(
        "--error", help="Enable exceptions and print output. Monsters here.", action="store_true")
    parser.add_argument("-t", "--timeout", type=int, help="Timeout for Z3 in ms (default "+str(global_params.TIMEOUT)+" ms).")
    parser.add_argument(
        "-v", "--verbose", help="Verbose output, print everything.", action="store_true")
    parser.add_argument(
        "-r", "--report", help="Create .report file.", action="store_true")
    parser.add_argument("-gb", "--globalblockchain",
                        help="Integrate with the global ethereum blockchain", action="store_true")
    parser.add_argument("-dl", "--depthlimit", help="Limit DFS depth (default "+str(global_params.DEPTH_LIMIT)+").",
                        action="store", dest="depth_limit", type=int)
    parser.add_argument("-gl", "--gaslimit", help="Limit Gas (default "+str(global_params.GAS_LIMIT)+").",
                        action="store", dest="gas_limit", type=int)
    parser.add_argument(
        "-st", "--state", help="Get input state from state.json", action="store_true")
    parser.add_argument("-ll", "--looplimit", help="Limit number of loops (default "+str(global_params.LOOP_LIMIT)+").",
                        action="store", dest="loop_limit", type=int)
    parser.add_argument(
        "-w", "--web", help="Run Osiris for web service", action="store_true")
    parser.add_argument("-glt", "--global-timeout", help="Timeout for symbolic execution in sec (default "+str(global_params.GLOBAL_TIMEOUT)+" sec).", action="store", dest="global_timeout", type=int)
    parser.add_argument(
        "-a", "--assertion", help="Check assertion failures.", action="store_true")
    parser.add_argument(
            "--debug", help="Display debug information", action="store_true")
    parser.add_argument(
        "--generate-test-cases", help="Generate test cases each branch of symbolic execution tree", action="store_true")
    parser.add_argument(
        "-c", "--cfg", help="Create control flow graph and store as .dot file.", action="store_true")
    parser.add_argument(
        "-m", "--model", help="Output models generated by the solver.", action="store_true")

    args = parser.parse_args()

    # Set global arguments for symbolic execution
    if args.timeout:
        global_params.TIMEOUT = args.timeout

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    global_params.PRINT_PATHS = 1 if args.paths else 0
    global_params.REPORT_MODE = 1 if args.report else 0
    global_params.IGNORE_EXCEPTIONS = 1 if args.error else 0
    global_params.USE_GLOBAL_BLOCKCHAIN = 1 if args.globalblockchain else 0
    global_params.INPUT_STATE = 1 if args.state else 0
    global_params.WEB = 1 if args.web else 0
    global_params.STORE_RESULT = 1 if args.json else 0
    global_params.CHECK_ASSERTIONS = 1 if args.assertion else 0
    global_params.DEBUG_MODE = 1 if args.debug else 0
    global_params.GENERATE_TEST_CASES = 1 if args.generate_test_cases else 0
    global_params.CFG = 1 if args.cfg else 0
    global_params.MODEL_INPUT = 1 if args.model else 0

    if args.depth_limit:
        global_params.DEPTH_LIMIT = args.depth_limit
    if args.gas_limit:
        global_params.GAS_LIMIT = args.gas_limit
    if args.loop_limit:
        global_params.LOOP_LIMIT = args.loop_limit
    if global_params.WEB:
        if args.global_timeout and args.global_timeout < global_params.GLOBAL_TIMEOUT:
            global_params.GLOBAL_TIMEOUT = args.global_timeout
    else:
        if args.global_timeout:
            global_params.GLOBAL_TIMEOUT = args.global_timeout

    # Check that our system has everything we need (evm, Z3)
    if not has_dependencies_installed():
        return

    # Retrieve contract from remote URL, if necessary
    if args.remote_URL:
        r = requests.get(args.remote_URL)
        code = r.text
        filename = "remote_contract.evm" if args.bytecode else "remote_contract.sol"
        if "etherscan.io" in args.remote_URL and not args.bytecode:
            try:
                filename = re.compile('<td>Contract<span class="hidden-su-xs"> Name</span>:</td><td>(.+?)</td>').findall(code.replace('\n','').replace('\t',''))[0].replace(' ', '')
                filename += ".sol"
            except:
                pass
            code = re.compile("<pre class='js-sourcecopyarea' id='editor' style='.+?'>([\s\S]+?)</pre>", re.MULTILINE).findall(code)[0]
            code = HTMLParser().unescape(code)
        args.source = filename
        with open(filename, 'w') as f:
            f.write(code)

    # If we are given bytecode, disassemble first, as we need to operate on EVM ASM.
    if args.bytecode:
        processed_evm_file = args.source + '.evm'
        disasm_file = args.source + '.evm.disasm'
        with open(args.source) as f:
            evm = f.read()

        with open(processed_evm_file, 'w') as f:
            f.write(removeSwarmHash(evm))

        analyze(processed_evm_file, disasm_file)

        remove_temporary_file(disasm_file)
        remove_temporary_file(processed_evm_file)
        remove_temporary_file(disasm_file + '.log')

        if global_params.UNIT_TEST == 2 or global_params.UNIT_TEST == 3:
            exit_code = os.WEXITSTATUS(cmd)
            if exit_code != 0:
                exit(exit_code)
    else:
        # Compile contracts using solc
        contracts = compileContracts(args.source)

        # Analyze each contract
        for cname, bin_str in contracts:
            print("")
            logging.info("Contract %s:", cname)
            processed_evm_file = cname + '.evm'
            disasm_file = cname + '.evm.disasm'

            with open(processed_evm_file, 'w') as of:
                of.write(removeSwarmHash(bin_str))

            analyze(processed_evm_file, disasm_file, SourceMap(cname, args.source))

            remove_temporary_file(processed_evm_file)
            remove_temporary_file(disasm_file)
            remove_temporary_file(disasm_file + '.log')

            if args.evm:
                with open(processed_evm_file, 'w') as of:
                    of.write(bin_str)

        if global_params.STORE_RESULT:
            if ':' in cname:
                result_file = os.path.join(global_params.RESULTS_DIR, cname.split(':')[0].replace('.sol', '.json').split('/')[-1])
                with open(result_file, 'a') as of:
                    of.write("}")

if __name__ == '__main__':
    main()
