pragma solidity ^0.4.19;

contract IntSignedUnsignedConversion {

  // Unsigned to signed conversion

  function unsignedToSigned1(int a, uint b) {
    if (a > int(b)) doSomething();
  }
  /*function unsignedToSigned2(int a, uint b) {
    if (a < int(b)) doSomething();
  }
  function unsignedToSigned3(int a, uint b) {
    if (a >= int(b)) doSomething();
  }
  function unsignedToSigned4(int a, uint b) {
    if (a <= int(b)) doSomething();
  }

  function unsignedToSigned1(uint a, int b) {
    if (int(a) > b) doSomething();
  }
  function unsignedToSigned2(uint a, int b) {
    if (int(a) < b) doSomething();
  }
  function unsignedToSigned3(uint a, int b) {
    if (int(a) >= b) doSomething();
  }
  function unsignedToSigned4(uint a, int b) {
    if (int(a) <= b) doSomething();
  }

  function unsignedToSigned1(uint a, uint b) {
    if (int(a) > int(b)) doSomething();
  }
  function unsignedToSigned2(uint a, uint b) {
    if (int(a) < int(b)) doSomething();
  }
  function unsignedToSigned3(uint a, uint b) {
    if (int(a) >= int(b)) doSomething();
  }
  function unsignedToSigned4(uint a, uint b) {
    if (int(a) <= int(b)) doSomething();
  }*/

  // Signed to unsigned conversion

  function signedToUnsigned1(int32 a, uint32 b) {
    if (uint32(a) > b) doSomething();
  }
  /*function signedToUnsigned2(int a, uint b) {
    if (a < int(b)) doSomething();
  }
  function signedToUnsigned3(int a, uint b) {
    if (a >= int(b)) doSomething();
  }
  function signedToUnsigned4(int a, uint b) {
    if (a <= int(b)) doSomething();
  }

  function unsignedToSigned1(uint a, int b) {
    if (int(a) > b) doSomething();
  }
  function unsignedToSigned2(uint a, int b) {
    if (int(a) < b) doSomething();
  }
  function unsignedToSigned3(uint a, int b) {
    if (int(a) >= b) doSomething();
  }
  function unsignedToSigned4(uint a, int b) {
    if (int(a) <= b) doSomething();
  }

  function unsignedToSigned1(uint a, uint b) {
    if (int(a) > int(b)) doSomething();
  }
  function unsignedToSigned2(uint a, uint b) {
    if (int(a) < int(b)) doSomething();
  }
  function unsignedToSigned3(uint a, uint b) {
    if (int(a) >= int(b)) doSomething();
  }
  function unsignedToSigned4(uint a, uint b) {
    if (int(a) <= int(b)) doSomething();
  }*/

  function doSomething() {}

}
