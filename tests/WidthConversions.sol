pragma solidity ^0.4.19;

contract C {

    uint32 max1;
    function unsignedWidthConversion1(uint _max) {
      max1 = uint32(_max);
    }
    uint64 max2;
    function unsignedWidthConversion2(uint64 _max) {
      max2 = _max;
    }


    int32 min1;
    function signedWidthConversion1(int _min) {
        min1 = int32(_min);
    }
    int64 min2;
    function signedWidthConversion2(int64 _min) {
        min2 = _min;
    }

}
