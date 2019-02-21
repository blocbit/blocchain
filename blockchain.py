from functools import reduce
import hashlib as hl

import json
import pickle
import requests
import time

# Import two functions from our hash_util.py file. Omit the ".py" in the import
from utility.hash_util import hash_block
from utility.verification import Verification
from block import Block
from submission import Submission
from wallet import Wallet

# The reward we give to miners (for creating a new block)
WIN_VOTE = 10

print(__name__)


class Blockchain:
    """The Blockchain class manages the chain of blocks as well as open
    submissions and the node on which it's running.

    Attributes:
        :chain: The list of blocks
        :open_submissions (private): The list of open submissions
        :hosting_node: The connected node (which runs the blockchain).
    """

    def __init__(self, public_key, node_id):
        """The constructor of the Blockchain class."""
        # Our starting block for the blockchain
        genesis_block = Block(0, '', [], 86400, 1577836799)
        # Initializing our (empty) blockchain list
        self.chain = [genesis_block]
        # Unhandled submissions
        self.__open_submissions = []
        self.public_key = public_key
        self.__peer_nodes = set()
        self.node_id = node_id
        self.resolve_conflicts = False
        self.load_data()

    # This turns the chain attribute into a property with a getter (the method
    # below) and a setter (@chain.setter)
    @property
    def chain(self):
        return self.__chain[:]

    # The setter for the chain property
    @chain.setter
    def chain(self, val):
        self.__chain = val

    def get_open_submissions(self):
        """Returns a copy of the open submissions list."""
        return self.__open_submissions[:]

    def load_data(self):
        """Initialize blockchain + open submissions data from a file."""
        try:
            with open('blockchain-{}.txt'.format(self.node_id), mode='r') as f:
                # file_content = pickle.loads(f.read())
                file_content = f.readlines()
                # blockchain = file_content['chain']
                # open_submissions = file_content['ot']
                blockchain = json.loads(file_content[0][:-1])
                # We need to convert  the loaded data because submissions
                # should use OrderedDict
                updated_blockchain = []
                for block in blockchain:
                    converted_tx = [Submission(
                        tx['sender'],
                        tx['recipient'],
                        tx['zero'],         #added to hold zero day countdown
                        tx['signature'],
                        tx['amount']) for tx in block['submissions']]
                    updated_block = Block(
                        block['index'],
                        block['previous_hash'],
                        converted_tx,
                        block['proof'],
                        block['timestamp'])
                    updated_blockchain.append(updated_block)
                self.chain = updated_blockchain
                open_submissions = json.loads(file_content[1][:-1])
                # We need to convert  the loaded data because submissions
                # should use OrderedDict
                updated_submissions = []
                for tx in open_submissions:
                    updated_submission = Submission(
                        tx['sender'],
                        tx['recipient'],
                        tx['zero'],
                        tx['signature'],
                        tx['amount'])
                    updated_submissions.append(updated_submission)
                self.__open_submissions = updated_submissions
                peer_nodes = json.loads(file_content[2])
                self.__peer_nodes = set(peer_nodes)
        except (IOError, IndexError):
            pass
        finally:
            print('Cleanup!')

    def save_data(self):
        """Save blockchain + open submissions snapshot to a file."""
        try:
            with open('blockchain-{}.txt'.format(self.node_id), mode='w') as f:
                saveable_chain = [
                    block.__dict__ for block in
                    [
                        Block(block_el.index,
                              block_el.previous_hash,
                              [tx.__dict__ for tx in block_el.submissions],
                              block_el.proof,
                              block_el.timestamp) for block_el in self.__chain
                    ]
                ]
                f.write(json.dumps(saveable_chain))
                f.write('\n')
                saveable_tx = [tx.__dict__ for tx in self.__open_submissions]
                f.write(json.dumps(saveable_tx))
                f.write('\n')
                f.write(json.dumps(list(self.__peer_nodes)))
                # save_data = {
                #     'chain': blockchain,
                #     'ot': open_submissions
                # }
                # f.write(pickle.dumps(save_data))
        except IOError:
            print('Saving failed!')

    def proof_of_work(self):
        """Generate a proof of work for the open submissions, the hash of the
        previous block and a random number (which is guessed until it fits)."""
        last_block = self.__chain[-1]
        last_hash = hash_block(last_block)
        proof = 0
        # Try different PoW numbers and return the first valid one
        while not Verification.valid_proof(
            self.__open_submissions,
            last_hash, proof
        ):
            proof += 1
        return proof

    def get_balance(self, sender=None):
        """Calculate and return the balance for a participant.
        """
        if sender is None:
            if self.public_key is None:
                return None
            participant = self.public_key
        else:
            participant = sender
        # Fetch a list of all sent coin amounts for the given person (empty
        # lists are returned if the person was NOT the sender)
        # This fetches sent amounts of submissions that were already included
        # in blocks of the blockchain
        tx_sender = [[tx.amount for tx in block.submissions
                      if tx.sender == participant] for block in self.__chain]
        # Fetch a list of all sent coin amounts for the given person (empty
        # lists are returned if the person was NOT the sender)
        # This fetches sent amounts of open submissions (to avoid double
        # spending)
        open_tx_sender = [
            tx.amount for tx in self.__open_submissions
            if tx.sender == participant
        ]
        tx_sender.append(open_tx_sender)
        print(tx_sender)
        amount_sent = reduce(lambda tx_sum, tx_amt: tx_sum + sum(tx_amt)
                             if len(tx_amt) > 0 else tx_sum + 0, tx_sender, 0)
        # This fetches received coin amounts of submissions that were already
        # included in blocks of the blockchain
        # We ignore open submissions here because you shouldn't be able to
        # spend coins before the submission was confirmed + included in a
        # block
        tx_recipient = [
            [
                tx.amount for tx in block.submissions
                if tx.recipient == participant
            ] for block in self.__chain
        ]
        amount_received = reduce(
            lambda tx_sum, tx_amt: tx_sum + sum(tx_amt)
            if len(tx_amt) > 0 else tx_sum + 0,
            tx_recipient,
            0
        )
        # Return the total balance
        return amount_received - amount_sent

    def get_last_blockchain_value(self):
        """ Returns the last value of the current blockchain. """
        if len(self.__chain) < 1:
            return None
        return self.__chain[-1]

    # This function accepts two arguments.
    # One required one (submission_amount) and one optional one
    # (last_submission)
    # The optional one is optional because it has a default value => [1]

    def add_submission(self,
                        recipient,
                        sender,
                        zero,
                        signature,
                        amount=1.0,
                        is_receiving=False):
        """ Append a new value as well as the last blockchain value to the blockchain.

        Arguments:
            :sender: The sender of the coins.
            :recipient: The recipient of the coins.
            :amount: The amount of coins sent with the submission
            (default = 1.0)
        """
        # submission = {
        #     'sender': sender,
        #     'recipient': recipient,
        #     'amount': amount
        # }
        # if self.public_key == None:
        #     return False
        submission = Submission(sender, recipient, zero, signature, amount)
        if Verification.verify_submission(submission, self.get_balance):
            self.__open_submissions.append(submission)
            self.save_data()
            if not is_receiving:
                for node in self.__peer_nodes:
                    url = 'http://{}/broadcast-submission'.format(node)
                    try:
                        response = requests.post(url,
                                                 json={
                                                     'sender': sender,
                                                     'recipient': recipient,
                                                     'zero': zero,
                                                     'amount': amount,
                                                     'signature': signature
                                                 })
                        if (response.status_code == 400 or
                                response.status_code == 500):
                            print('Submission declined, needs resolving')
                            return False
                    except requests.exceptions.ConnectionError:
                        continue
            return True
        return False

    def submission_zero(self):
        """Countdown to day zero,the  amount of days left until voting ends."""
        genesis_bloc = self.__chain[0]
        genesis_ts = genesis_bloc.timestamp
        genesis_pf = genesis_bloc.proof
        submission_zero = (genesis_ts - time.time()) // genesis_pf
        return submission_zero

    def mine_block(self):
        """Create a new block and add open submissions to it."""
        # Fetch the currently last block of the blockchain
        if self.public_key is None:
            return None
        last_block = self.__chain[-1]
        # Hash the last block (=> to be able to compare it to the stored hash
        # value)
        hashed_block = hash_block(last_block)
        proof = self.proof_of_work()
        # Added to avoid blockchain startup error after genesis bloxk as it contains no submission i.e. no zero
        last_pf = last_block.proof
        if last_pf != 86400:
            zero = self.submission_zero()           
        else:
            zero = 365.0
        # Miners should be rewarded, so let's create a reward submission
        # reward_submission = {
        #     'sender': 'MINING',
        #     'recipient': owner,
        #     'amount': MINING_REWARD
        # }
        reward_submission = Submission(
            'STATION', self.public_key, zero, '', WIN_VOTE)
        # Copy submission instead of manipulating the original
        # open_submissions list
        # This ensures that if for some reason the mining should fail,
        # we don't have the reward submission stored in the open submissions
        copied_submissions = self.__open_submissions[:]
        for tx in copied_submissions:
            if not Wallet.verify_submission(tx):
                return None
        copied_submissions.append(reward_submission)
        block = Block(len(self.__chain), hashed_block,
                      copied_submissions, proof)
        self.__chain.append(block)
        self.__open_submissions = []
        self.save_data()
        for node in self.__peer_nodes:
            url = 'http://{}/broadcast-block'.format(node)
            converted_block = block.__dict__.copy()
            converted_block['submissions'] = [
                tx.__dict__ for tx in converted_block['submissions']]
            try:
                response = requests.post(url, json={'block': converted_block})
                if response.status_code == 400 or response.status_code == 500:
                    print('Block declined, needs resolving')
                if response.status_code == 409:
                    self.resolve_conflicts = True
            except requests.exceptions.ConnectionError:
                continue
        return block

    def add_block(self, block):
        """Add a block which was received via broadcasting to the localb
        lockchain."""
        # Create a list of submission objects
        submissions = [Submission(
            tx['sender'],
            tx['recipient'],
            tx['zero'],
            tx['signature'],
            tx['amount']) for tx in block['submissions']]
        # Validate the proof of work of the block and store the result (True
        # or False) in a variable
        proof_is_valid = Verification.valid_proof(
            submissions[:-1], block['previous_hash'], block['proof'])
        # Check if previous_hash stored in the block is equal to the local
        # blockchain's last block's hash and store the result in a block
        hashes_match = hash_block(self.chain[-1]) == block['previous_hash']
        if not proof_is_valid or not hashes_match:
            return False
        # Create a Block object
        converted_block = Block(
            block['index'],
            block['previous_hash'],
            submissions,
            block['proof'],
            block['timestamp'])
        self.__chain.append(converted_block)
        stored_submissions = self.__open_submissions[:]
        # Check which open submissions were included in the received block
        # and remove them
        # This could be improved by giving each submission an ID that would
        # uniquely identify it
        for itx in block['submissions']:
            for opentx in stored_submissions:
                if (opentx.sender == itx['sender'] and
                        opentx.recipient == itx['recipient'] and
                        opentx.zero == itx['zero'] and
                        opentx.amount == itx['amount'] and
                        opentx.signature == itx['signature']):
                    try:
                        self.__open_submissions.remove(opentx)
                    except ValueError:
                        print('Item was already removed')
        self.save_data()
        return True

    def resolve(self):
        """Checks all peer nodes' blockchains and replaces the local one with
        longer valid ones."""
        # Initialize the winner chain with the local chain
        winner_chain = self.chain
        replace = False
        for node in self.__peer_nodes:
            url = 'http://{}/chain'.format(node)
            try:
                # Send a request and store the response
                response = requests.get(url)
                # Retrieve the JSON data as a dictionary
                node_chain = response.json()
                # Convert the dictionary list to a list of block AND
                # submission objects
                node_chain = [
                    Block(block['index'],
                          block['previous_hash'],
                          [
                        Submission(
                            tx['sender'],
                            tx['recipient'],
                            tx['zero'],
                            tx['signature'],
                            tx['amount']) for tx in block['submissions']
                    ],
                        block['proof'],
                        block['timestamp']) for block in node_chain
                ]
                node_chain_length = len(node_chain)
                local_chain_length = len(winner_chain)
                # Store the received chain as the current winner chain if it's
                # longer AND valid
                if (node_chain_length > local_chain_length and
                        Verification.verify_chain(node_chain)):
                    winner_chain = node_chain
                    replace = True
            except requests.exceptions.ConnectionError:
                continue
        self.resolve_conflicts = False
        # Replace the local chain with the winner chain
        self.chain = winner_chain
        if replace:
            self.__open_submissions = []
        self.save_data()
        return replace

    def add_peer_node(self, node):
        """Adds a new node to the peer node set.

        Arguments:
            :node: The node URL which should be added.
        """
        self.__peer_nodes.add(node)
        self.save_data()

    def remove_peer_node(self, node):
        """Removes a node from the peer node set.

        Arguments:
            :node: The node URL which should be removed.
        """
        self.__peer_nodes.discard(node)
        self.save_data()

    def get_peer_nodes(self):
        """Return a list of all connected peer nodes."""
        return list(self.__peer_nodes)
