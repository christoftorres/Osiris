Osiris
======

![](https://img.icons8.com/color/200/000000/osiris.png)

An analysis tool to detect integer bugs in Ethereum smart contracts. Osiris is based on [Oyente](https://github.com/melonproject/oyente).

## Quick Start

A container with the dependencies set up can be found [here](https://hub.docker.com/r/christoftorres/osiris/).

To open the container, install docker and run:

```
docker pull christoftorres/osiris && docker run -i -t christoftorres/osiris
```

To evaluate the SimpleDAO contract inside the container, run:

```
python osiris/osiris.py -s datasets/SimpleDAO/SimpleDAO_0.4.19.sol
```

and you are done!

## Custom Docker image build

```
docker build -t osiris .
docker run -it osiris:latest
```

## Full installation

### Install the following dependencies
#### solc
```
$ sudo add-apt-repository ppa:ethereum/ethereum
$ sudo apt-get update
$ sudo apt-get install solc
```

#### evm from [go-ethereum](https://github.com/ethereum/go-ethereum)

1. https://geth.ethereum.org/downloads/ or
2. By from PPA if your using Ubuntu
```
$ sudo apt-get install software-properties-common
$ sudo add-apt-repository -y ppa:ethereum/ethereum
$ sudo apt-get update
$ sudo apt-get install ethereum
```

#### [z3](https://github.com/Z3Prover/z3/releases) Theorem Prover version 4.6.0.

Download the [source code of version z3-4.6.0](https://github.com/Z3Prover/z3/releases/tag/z3-4.6.0)

Install z3 using Python bindings

```
$ python scripts/mk_make.py --python
$ cd build
$ make
$ sudo make install
```

#### [Requests](https://github.com/kennethreitz/requests/) library

```
pip install requests
```

#### [web3](https://github.com/pipermerriam/web3.py) library

```
pip install web3
```

#### [pysha3](https://github.com/tiran/pysha3) library

```
pip install pysha3
```

### Evaluating Ethereum Contracts

```
#evaluate a local solidity contract
python osiris.py -s <contract filename>
```

Run ```python osiris.py --help``` for a complete list of options.
