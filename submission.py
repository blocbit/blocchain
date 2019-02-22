from collections import OrderedDict

from utility.printable import Printable


class Submission(Printable):
    """A submission which can be added to a block in the blockchain.

    Attributes:
        :voter: The person voting.
        :candidate: The candidate recieving the votes.
        :signature: The signature for the submission.
        :amount: The amount of coins sent.
    """

    def __init__(self, voter, candidate, zero, signature, amount):
        self.voter = voter
        self.candidate = candidate
        self.zero = zero
        self.amount = amount
        self.signature = signature

    def to_ordered_dict(self):
        """Converts this submission into a (hashable) OrderedDict."""
        return OrderedDict([('voter', self.voter),
                            ('candidate', self.candidate),
                            ('zero', self.zero),
                            ('amount', self.amount)])
