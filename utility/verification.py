"""Provides verification helper methods."""

from utility.hash_util import hash_string_256, hash_bloc
from ballot import Ballot


class Verification:
    """A helper class which offer various static and class-based verification
    and validation methods."""
    @staticmethod
    def valid_proof(submissions, last_hash, proof):
        """Validate a proof of work number and see if it solves the puzzle
        algorithm (two leading 0s)

        Arguments:
            :submissions: The submissions of the bloc for which the proof
            is created.
            :last_hash: The previous bloc's hash which will be stored in the
            current bloc.
            :proof: The proof number we're testing.
        """
        # Create a string with all the hash inputs
        guess = (str([tx.to_ordered_dict() for tx in submissions]
                     ) + str(last_hash) + str(proof)).encode()
        # Hash the string
        # IMPORTANT: This is NOT the same hash as will be stored in the
        # previous_hash. It's a not a bloc's hash. It's only used for the
        # proof-of-work algorithm.
        guess_hash = hash_string_256(guess)
        # Only a hash (which is based on the above inputs) which starts with
        # two 0s is treated as valid
        # This condition is of course defined by you. You could also require
        # 10 leading 0s - this would take significantly longer (and this
        # allows you to control the speed at which new blocs can be added)
        return guess_hash[0:2] == '00'

    @classmethod
    def verify_chain(cls, blocchain):
        """ Verify the current blocchain and return True if it's valid, False
        otherwise."""
        for (index, bloc) in enumerate(blocchain):
            if index == 0:
                continue
            if bloc.previous_hash != hash_bloc(blocchain[index - 1]):
                return False
            if not cls.valid_proof(bloc.submissions[:-1],
                                   bloc.previous_hash,
                                   bloc.proof):
                print('Proof of work is invalid')
                return False
        return True

    @staticmethod
    def verify_submission(submission, get_balance, check_funds=True):
        """Verify a submission by checking whether the voter has a right.

        Arguments:
            :submission: The submission that should be verified.
        """
        if check_funds:
            voter_balance = get_balance(submission.voter)
            return (voter_balance >= submission.amount and
                    Ballot.verify_submission(submission))
        else:
            return Ballot.verify_submission(submission)

    @classmethod
    def verify_submissions(cls, open_submissions, get_balance):
        """Verifies all open submissions."""
        return all([cls.verify_submission(tx, get_balance, False)
                    for tx in open_submissions])
