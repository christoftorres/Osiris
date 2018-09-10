// https://dasp.co/#item-3

pragma solidity ^0.4.21;

contract ArrayOfThings {

  bytes32[] public arrayOfThings;

  function popArrayOfThings() {
  	require(arrayOfThings.length >= 0);
  	arrayOfThings.length--;
  }

}
