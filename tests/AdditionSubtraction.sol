contract C {

    mapping (address => uint) public unsignedBalanceOf;
    mapping (address => int32) public signedBalanceOf;

    // Unsigned overflow/underflow
    function transfer1(address _to, uint _value) {
        //require(unsignedBalanceOf[msg.sender] > _value);
        //require(unsignedBalanceOf[_to] + _value >= unsignedBalanceOf[_to] && unsignedBalanceOf[msg.sender] > _value);
        //require(unsignedBalanceOf[msg.sender] > _value && unsignedBalanceOf[_to] + _value >= unsignedBalanceOf[_to]);
        unsignedBalanceOf[msg.sender] -= _value;
        //require(unsignedBalanceOf[_to] + _value >= unsignedBalanceOf[_to]);
        unsignedBalanceOf[_to] += _value;
    }

    // Signed overflow/underflow
    function transfer2(address _to, int32 _value) {
        if (((_value > 0) && (signedBalanceOf[msg.sender] > (int32(2**(32-1)) + _value))) || ((_value < 0) && (signedBalanceOf[msg.sender] > (int32(2**(32-1)-1) + _value)))) { throw; }
        signedBalanceOf[msg.sender] -= _value;
        if (((_value > 0) && (signedBalanceOf[_to] > (int32(2**(32-1)-1) - _value))) || ((_value < 0) && (signedBalanceOf[_to] < (int32(-2**(32-1)) - _value)))) { throw; }
        signedBalanceOf[_to] += _value;
    }

    function test(int128 x, int128 y) returns (int r) {
      if (((y > 0) && (x > (int128(2**(128-1)-1) - y))) || ((y < 0) && (x < (int128(-2**(128-1)) - y)))) { throw; }
      r = x + y;
    }
}
