// https://dasp.co/#item-3

pragma solidity ^0.4.21;

contract Voting {

  event deletePost(uint postId);

  function votes(uint postId, uint upvote, uint downvotes) public {
  	if (upvote - downvotes < 0) {
  		deletePost(postId);
  	}
  }

}
