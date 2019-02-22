from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA256
import Crypto.Random
import binascii


class Ballot:
    """Creates, loads and holds private and public keys. Manages submission
    signing and verification."""

    def __init__(self, node_id):
        self.private_key = None
        self.public_key = None
        self.node_id = node_id

    def create_keys(self):
        """Create a new pair of private and public keys."""
        private_key, public_key = self.generate_keys()
        self.private_key = private_key
        self.public_key = public_key

    def save_keys(self):
        """Saves the keys to a file (ballot.blc)."""
        if self.public_key is not None and self.private_key is not None:
            try:
                with open('ballot-{}.blc'.format(self.node_id), mode='w') as f:
                    f.write(self.public_key)
                    f.write('\n')
                    f.write(self.private_key)
                return True
            except (IOError, IndexError):
                print('Saving ballot failed...')
                return False

    def load_keys(self):
        """Loads the keys from the ballot.blc file into memory."""
        try:
            with open('ballot-{}.blc'.format(self.node_id), mode='r') as f:
                keys = f.readlines()
                public_key = keys[0][:-1]
                private_key = keys[1]
                self.public_key = public_key
                self.private_key = private_key
            return True
        except (IOError, IndexError):
            print('Loading ballot failed...')
            return False

    def generate_keys(self):
        """Generate a new pair of private and public key."""
        private_key = RSA.generate(1024, Crypto.Random.new().read)
        public_key = private_key.publickey()
        return (
            binascii
            .hexlify(private_key.exportKey(format='DER'))
            .decode('ascii'),
            binascii
            .hexlify(public_key.exportKey(format='DER'))
            .decode('ascii')
        )

    def sign_submission(self, voter, candidate, zero, amount):
        """Sign a submission and return the signature.

        Arguments:
            :voter: The submission voter.
            :candidate: The candidate for the submission.
            :amount: The amount of the submission.
        """
        signer = PKCS1_v1_5.new(RSA.importKey(
            binascii.unhexlify(self.private_key)))
        h = SHA256.new((str(voter) + str(candidate) + str(zero) +
                        str(amount)).encode('utf8'))
        signature = signer.sign(h)
        return binascii.hexlify(signature).decode('ascii')

    @staticmethod
    def verify_submission(submission):
        """Verify the signature of a submission.

        Arguments:
            :submission: The submission that should be verified.
        """
        public_key = RSA.importKey(binascii.unhexlify(submission.voter))
        verifier = PKCS1_v1_5.new(public_key)
        h = SHA256.new((str(submission.voter) + str(submission.candidate) + str(submission.zero) +
                        str(submission.amount)).encode('utf8'))
        return verifier.verify(h, binascii.unhexlify(submission.signature))
