// https://dasp.co/#item-3

pragma solidity ^0.4.21;

contract Withdraw {

  mapping (address => uint) public balances;

  function withdraw(uint _amount) public payable {
  	require(balances[msg.sender] - _amount >= 0);
  	msg.sender.transfer(_amount);
  	balances[msg.sender] -= _amount;
  }

}
