contract Multiplication {

    function unsigned_multiplication(uint x, uint y) returns (uint r) {
      //if (x != 0 && y / x != y) { throw; }
      r = x * y;
    }

    function signed_multiplication(int32 x, int32 y) returns (int r) {
        if (x > 0) {
          if (y > 0) {
            if (x > int32(2**(32-1)-1) / y) {
              throw;
            }
          } else {
            if (y < int32(-2**(32-1)) / x) {
              throw;
            }
          }
        } else {
          if (y > 0) {
            if (x < int32(-2**(32-1)) / y) {
              throw;
            }
          } else {
            if (x != 0 && y < int32(2**(32-1)-1) / x) {
              throw;
            }
          }
        }
        r = x * y;
    }

}
