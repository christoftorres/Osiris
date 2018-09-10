contract Division {

    /*function unsigned_division(uint32 x, uint32 y) returns (int r) {
      //if (y == 0) { throw; }
      r = x / y;
    }*/

    function signed_division(int x, int y) returns (int) {
      //if ((y == 0) || ((x == -2**255) && (y == -1))) { throw; }
      return x / y;
    }

}
