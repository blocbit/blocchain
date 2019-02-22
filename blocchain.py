from functools import reduce
import hashlib as hl

import json
#import pickle
import requests
import time

# Import two functions from our hash_util.py file. Omit the ".py" in the import
from utility.hash_util import hash_bloc
from utility.verification import Verification
from bloc import Bloc
from submission import Submission
from ballot import Ballot

# The reward we give to miners (for creating a new bloc)
VOTE_WINDOW = True

print(__name__)


class Blocchain:
    """The Blocchain class manages the chain of blocs as well as open
    submissions and the node on which it's running.

    Attributes:
        :chain: The list of blocs
        :open_submissions (private): The list of open submissions
        :hosting_node: The connected node (which runs the blocchain).
    """

    def __init__(self, public_key, node_id):
        """The constructor of the Blocchain class."""
        # Our starting bloc for the blocchain
        genesis_bloc = Bloc(0, '', [], 86400, 1577836799)
        # Initializing our (empty) blocchain list
        self.chain = [genesis_bloc]
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
        """Initialize blocchain + open submissions data from a file."""
        try:
            with open('blocchain-{}.bit'.format(self.node_id), mode='r') as f:
                # file_content = pickle.loads(f.read())
                file_content = f.readlines()
                # blocchain = file_content['chain']
                # open_submissions = file_content['ot']
                blocchain = json.loads(file_content[0][:-1])
                # We need to convert  the loaded data because submissions
                # should use OrderedDict
                updated_blocchain = []
                for bloc in blocchain:
                    converted_tx = [Submission(
                        tx['voter'],
                        tx['candidate'],
                        tx['zero'],         #added to hold zero day countdown
                        tx['signature'],
                        tx['amount']) for tx in bloc['submissions']]
                    updated_bloc = Bloc(
                        bloc['index'],
                        bloc['previous_hash'],
                        converted_tx,
                        bloc['proof'],
                        bloc['timestamp'])
                    updated_blocchain.append(updated_bloc)
                self.chain = updated_blocchain
                open_submissions = json.loads(file_content[1][:-1])
                # We need to convert  the loaded data because submissions
                # should use OrderedDict
                updated_submissions = []
                for tx in open_submissions:
                    updated_submission = Submission(
                        tx['voter'],
                        tx['candidate'],
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
        """Save blocchain + open submissions snapshot to a file."""
        try:
            with open('blocchain-{}.bit'.format(self.node_id), mode='w') as f:
                saveable_chain = [
                    bloc.__dict__ for bloc in
                    [
                        Bloc(bloc_el.index,
                              bloc_el.previous_hash,
                              [tx.__dict__ for tx in bloc_el.submissions],
                              bloc_el.proof,
                              bloc_el.timestamp) for bloc_el in self.__chain
                    ]
                ]
                f.write(json.dumps(saveable_chain))
                f.write('\n')
                saveable_tx = [tx.__dict__ for tx in self.__open_submissions]
                f.write(json.dumps(saveable_tx))
                f.write('\n')
                f.write(json.dumps(list(self.__peer_nodes)))
                # save_data = {
                #     'chain': blocchain,
                #     'ot': open_submissions
                # }
                # f.write(pickle.dumps(save_data))
        except IOError:
            print('Saving failed!')

    def proof_of_work(self):
        """Generate a proof of work for the open submissions, the hash of the
        previous bloc and a random number (which is guessed until it fits)."""
        last_bloc = self.__chain[-1]
        last_hash = hash_bloc(last_bloc)
        proof = 0
        # Try different PoW numbers and return the first valid one
        while not Verification.valid_proof(
            self.__open_submissions,
            last_hash, proof
        ):
            proof += 1
        return proof

    def get_balance(self, voter=None):
        """Calculate and return the balance for a participant.
        """
        if voter is None:
            if self.public_key is None:
                return None
            participant = self.public_key
        else:
            participant = voter
        # Fetch a list of all sent coin amounts for the given person (empty
        # lists are returned if the person was NOT the voter)
        # This fetches sent amounts of submissions that were already included
        # in blocs of the blocchain
        tx_voter = [[tx.amount for tx in bloc.submissions
                      if tx.voter == participant] for bloc in self.__chain]
        # Fetch a list of all sent coin amounts for the given person (empty
        # lists are returned if the person was NOT the voter)
        # This fetches sent amounts of open submissions (to avoid double
        # spending)
        open_tx_voter = [
            tx.amount for tx in self.__open_submissions
            if tx.voter == participant
        ]
        tx_voter.append(open_tx_voter)
        print(tx_voter)
        amount_sent = reduce(lambda tx_sum, tx_amt: tx_sum + sum(tx_amt)
                             if len(tx_amt) > 0 else tx_sum + 0, tx_voter, 0)
        # This fetches received coin amounts of submissions that were already
        # included in blocs of the blocchain
        # We ignore open submissions here because you shouldn't be able to
        # spend coins before the submission was confirmed + included in a
        # bloc
        tx_candidate = [
            [
                tx.amount for tx in bloc.submissions
                if tx.candidate == participant
            ] for bloc in self.__chain
        ]
        amount_received = reduce(
            lambda tx_sum, tx_amt: tx_sum + sum(tx_amt)
            if len(tx_amt) > 0 else tx_sum + 0,
            tx_candidate,
            0
        )
        # Return the total balance
        return amount_received - amount_sent

    def get_last_blocchain_value(self):
        """ Returns the last value of the current blocchain. """
        if len(self.__chain) < 1:
            return None
        return self.__chain[-1]

    # This function accepts two arguments.
    # One required one (submission_amount) and one optional one
    # (last_submission)
    # The optional one is optional because it has a default value => [1]

    def add_submission(self,
                        candidate,
                        voter,
                        zero,
                        signature,
                        amount=1.0,
                        is_receiving=False):
        """ Append a new value as well as the last blocchain value to the blocchain.

        Arguments:
            :voter: The person voting.
            :candidate: The candidate recieving the votes.
            :amount: The amount of coins sent with the submission
            (default = 1.0)
        """
        # submission = {
        #     'voter': voter,
        #     'candidate': candidate,
        #     'amount': amount
        # }
        # if self.public_key == None:
        #     return False
        submission = Submission(voter, candidate, zero, signature, amount)
        if Verification.verify_submission(submission, self.get_balance):
            self.__open_submissions.append(submission)
            self.save_data()
            if not is_receiving:
                for node in self.__peer_nodes:
                    url = 'http://{}/broadcast-submission'.format(node)
                    try:
                        response = requests.post(url,
                                                 json={
                                                     'voter': voter,
                                                     'candidate': candidate,
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

    def mine_bloc(self):
        global VOTE_WINDOW
        """Create a new bloc and add open submissions to it."""
        # Fetch the currently last bloc of the blocchain
        if self.public_key is None:
            return None
        last_bloc = self.__chain[-1]
        last_pf = last_bloc.proof
        #window = self.load_window_data()
        # Hash the last bloc (=> to be able to compare it to the stored hash
        # value)
        hashed_bloc = hash_bloc(last_bloc)
        proof = self.proof_of_work()
        # Added to avoid blocchain startup error after genesis bloxk as it contains no submission i.e. no zero
        last_pf = last_bloc.proof
        if last_pf != 86400:
            zero = self.submission_zero()           
        else:
            zero = 365.0
        # Voters have the right to vote daily, so let's create a window submission
        # reward_submission = {
        #     'voter': 'STATION',
        #     'candidate': owner,
        #     'amount': 0 or 1
        # }
        Window_open = Submission(
            'STATION', self.public_key, zero, '', 1)
        Window_closed = Submission(
            'STATION', self.public_key, zero, '', 0)
        # Copy submission instead of manipulating the original
        # open_submissions list
        # This ensures that if for some reason the mining should fail,
        # we don't have the reward submission stored in the open submissions
        copied_submissions = self.__open_submissions[:]
        for tx in copied_submissions:
            if not Ballot.verify_submission(tx):
                return None
        
        # if global var is set to true award right and then set back to false
        if VOTE_WINDOW is False:
            copied_submissions.append(Window_closed)
        else:
            copied_submissions.append(Window_open)
            VOTE_WINDOW = False
        bloc = Bloc(len(self.__chain), hashed_bloc,
                      copied_submissions, proof)
        self.__chain.append(bloc)
        self.__open_submissions = []
        self.save_data()
        for node in self.__peer_nodes:
            url = 'http://{}/broadcast-bloc'.format(node)
            converted_bloc = bloc.__dict__.copy()
            converted_bloc['submissions'] = [
                tx.__dict__ for tx in converted_bloc['submissions']]
            try:
                response = requests.post(url, json={'bloc': converted_bloc})
                if response.status_code == 400 or response.status_code == 500:
                    print('Bloc declined, needs resolving')
                if response.status_code == 409:
                    self.resolve_conflicts = True
            except requests.exceptions.ConnectionError:
                continue
        return bloc

    def add_bloc(self, bloc):
        """Add a bloc which was received via broadcasting to the localb
        lockchain."""
        # Create a list of submission objects
        submissions = [Submission(
            tx['voter'],
            tx['candidate'],
            tx['zero'],
            tx['signature'],
            tx['amount']) for tx in bloc['submissions']]
        # Validate the proof of work of the bloc and store the result (True
        # or False) in a variable
        proof_is_valid = Verification.valid_proof(
            submissions[:-1], bloc['previous_hash'], bloc['proof'])
        # Check if previous_hash stored in the bloc is equal to the local
        # blocchain's last bloc's hash and store the result in a bloc
        hashes_match = hash_bloc(self.chain[-1]) == bloc['previous_hash']
        if not proof_is_valid or not hashes_match:
            return False
        # Create a bloc object
        converted_bloc = Bloc(
            bloc['index'],
            bloc['previous_hash'],
            submissions,
            bloc['proof'],
            bloc['timestamp'])
        self.__chain.append(converted_bloc)
        stored_submissions = self.__open_submissions[:]
        # Check which open submissions were included in the received bloc
        # and remove them
        # This could be improved by giving each submission an ID that would
        # uniquely identify it
        for itx in bloc['submissions']:
            for opentx in stored_submissions:
                if (opentx.voter == itx['voter'] and
                        opentx.candidate == itx['candidate'] and
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
        """Checks all peer nodes' blocchains and replaces the local one with
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
                # Convert the dictionary list to a list of bloc AND
                # submission objects
                node_chain = [
                    Bloc(bloc['index'],
                          bloc['previous_hash'],
                          [
                        Submission(
                            tx['voter'],
                            tx['candidate'],
                            tx['zero'],
                            tx['signature'],
                            tx['amount']) for tx in bloc['submissions']
                    ],
                        bloc['proof'],
                        bloc['timestamp']) for bloc in node_chain
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
