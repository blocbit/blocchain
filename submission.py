from collections import OrderedDict

from utility.printable import Printable


class Submission(Printable):
    """A submission which can be added to a block in the blockchain.

    Attributes:
        :sender: The sender of the coins.
        :recipient: The recipient of the coins.
        :signature: The signature for the submission.
        :amount: The amount of coins sent.
    """

    def __init__(self, sender, recipient, zero, signature, amount):
        self.sender = sender
        self.recipient = recipient
        self.zero = zero
        self.amount = amount
        self.signature = signature

    def to_ordered_dict(self):
        """Converts this submission into a (hashable) OrderedDict."""
        return OrderedDict([('sender', self.sender),
                            ('recipient', self.recipient),
                            ('zero', self.zero),
                            ('amount', self.amount)])
