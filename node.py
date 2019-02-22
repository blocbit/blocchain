from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from ballot import Ballot
from blocchain import Blocchain

app = Flask(__name__)
CORS(app)


@app.route('/', methods=['GET'])
def get_node_ui():
    return send_from_directory('ui', 'node.html')


@app.route('/network', methods=['GET'])
def get_network_ui():
    return send_from_directory('ui', 'network.html')


@app.route('/ballot', methods=['POST'])
def create_keys():
    ballot.create_keys()
    if ballot.save_keys():
        global blocchain
        blocchain = Blocchain(ballot.public_key, port)
        response = {
            'public_key': ballot.public_key,
            'private_key': ballot.private_key,
            'funds': blocchain.get_balance()
        }
        return jsonify(response), 201
    else:
        response = {
            'message': 'Saving the keys failed.'
        }
        return jsonify(response), 500


@app.route('/ballot', methods=['GET'])
def load_keys():
    if ballot.load_keys():
        global blocchain
        blocchain = Blocchain(ballot.public_key, port)
        response = {
            'public_key': ballot.public_key,
            'private_key': ballot.private_key,
            'funds': blocchain.get_balance()
        }
        return jsonify(response), 201
    else:
        response = {
            'message': 'Loading the keys failed.'
        }
        return jsonify(response), 500


@app.route('/balance', methods=['GET'])
def get_balance():
    balance = blocchain.get_balance()
    if balance is not None:
        response = {
            'message': 'Fetched balance successfully.',
            'funds': balance
        }
        return jsonify(response), 200
    else:
        response = {
            'messsage': 'Loading balance failed.',
            'ballot_set_up': ballot.public_key is not None
        }
        return jsonify(response), 500


@app.route('/broadcast-submission', methods=['POST'])
def broadcast_submission():
    values = request.get_json()
    if not values:
        response = {'message': 'No data found.'}
        return jsonify(response), 400
    required = ['voter', 'candidate', 'amount', 'signature']
    if not all(key in values for key in required):
        response = {'message': 'Some data is missing.'}
        return jsonify(response), 400
    success = blocchain.add_submission(
        values['candidate'],
        values['voter'],
        values['zero'],
        values['signature'],
        values['amount'],
        is_receiving=True)
    if success:
        response = {
            'message': 'Successfully added submission.',
            'submission': {
                'voter': values['voter'],
                'candidate': values['candidate'],
                'zero': values['zero'],
                'amount': values['amount'],
                'signature': values['signature']
            }
        }
        return jsonify(response), 201
    else:
        response = {
            'message': 'Creating a submission failed.'
        }
        return jsonify(response), 500


@app.route('/broadcast-bloc', methods=['POST'])
def broadcast_bloc():
    values = request.get_json()
    if not values:
        response = {'message': 'No data found.'}
        return jsonify(response), 400
    if 'bloc' not in values:
        response = {'message': 'Some data is missing.'}
        return jsonify(response), 400
    bloc = values['bloc']
    if bloc['index'] == blocchain.chain[-1].index + 1:
        if blocchain.add_bloc(bloc):
            response = {'message': 'Bloc added'}
            return jsonify(response), 201
        else:
            response = {'message': 'Bloc seems invalid.'}
            return jsonify(response), 409
    elif bloc['index'] > blocchain.chain[-1].index:
        response = {
            'message': 'Blocchain seems to differ from local blocchain.'}
        blocchain.resolve_conflicts = True
        return jsonify(response), 200
    else:
        response = {
            'message': 'Blocchain seems to be shorter, bloc not added'}
        return jsonify(response), 409


@app.route('/submission', methods=['POST'])
def add_submission():
    if ballot.public_key is None:
        response = {
            'message': 'No ballot set up.'
        }
        return jsonify(response), 400
    values = request.get_json()
    if not values:
        response = {
            'message': 'No data found.'
        }
        return jsonify(response), 400
    required_fields = ['candidate', 'amount']
    if not all(field in values for field in required_fields):
        response = {
            'message': 'Required data is missing.'
        }
        return jsonify(response), 400
    candidate = values['candidate']
    amount = values['amount']
    zero = blocchain.submission_zero()
    signature = ballot.sign_submission(ballot.public_key, candidate, zero, amount)
    success = blocchain.add_submission(
        candidate, ballot.public_key, zero, signature, amount)
    if success:
        response = {
            'message': 'Successfully added submission.',
            'submission': {
                'voter': ballot.public_key,
                'candidate': candidate,
                'zero': zero,
                'amount': amount,
                'signature': signature
            },
            'funds': blocchain.get_balance()
        }
        return jsonify(response), 201
    else:
        response = {
            'message': 'Creating a submission failed.'
        }
        return jsonify(response), 500


@app.route('/mine', methods=['POST'])
def mine():
    if blocchain.resolve_conflicts:
        response = {'message': 'Resolve conflicts first, bloc not added!'}
        return jsonify(response), 409
    bloc = blocchain.mine_bloc()
    if bloc is not None:
        dict_bloc = bloc.__dict__.copy()
        dict_bloc['submissions'] = [
            tx.__dict__ for tx in dict_bloc['submissions']]
        response = {
            'message': 'Bloc added successfully.',
            'bloc': dict_bloc,
            'funds': blocchain.get_balance()
        }
        return jsonify(response), 201
    else:
        response = {
            'message': 'Adding a bloc failed.',
            'ballot_set_up': ballot.public_key is not None
        }
        return jsonify(response), 500


@app.route('/resolve-conflicts', methods=['POST'])
def resolve_conflicts():
    replaced = blocchain.resolve()
    if replaced:
        response = {'message': 'Chain was replaced!'}
    else:
        response = {'message': 'Local chain kept!'}
    return jsonify(response), 200


@app.route('/submissions', methods=['GET'])
def get_open_submission():
    submissions = blocchain.get_open_submissions()
    dict_submissions = [tx.__dict__ for tx in submissions]
    return jsonify(dict_submissions), 200


@app.route('/chain', methods=['GET'])
def get_chain():
    chain_snapshot = blocchain.chain
    dict_chain = [bloc.__dict__.copy() for bloc in chain_snapshot]
    for dict_bloc in dict_chain:
        dict_bloc['submissions'] = [
            tx.__dict__ for tx in dict_bloc['submissions']]
    return jsonify(dict_chain), 200


@app.route('/node', methods=['POST'])
def add_node():
    values = request.get_json()
    if not values:
        response = {
            'message': 'No data attached.'
        }
        return jsonify(response), 400
    if 'node' not in values:
        response = {
            'message': 'No node data found.'
        }
        return jsonify(response), 400
    node = values['node']
    blocchain.add_peer_node(node)
    response = {
        'message': 'Node added successfully.',
        'all_nodes': blocchain.get_peer_nodes()
    }
    return jsonify(response), 201


@app.route('/node/<node_url>', methods=['DELETE'])
def remove_node(node_url):
    if node_url == '' or node_url is None:
        response = {
            'message': 'No node found.'
        }
        return jsonify(response), 400
    blocchain.remove_peer_node(node_url)
    response = {
        'message': 'Node removed',
        'all_nodes': blocchain.get_peer_nodes()
    }
    return jsonify(response), 200


@app.route('/nodes', methods=['GET'])
def get_nodes():
    nodes = blocchain.get_peer_nodes()
    response = {
        'all_nodes': nodes
    }
    return jsonify(response), 200


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=5000)
    args = parser.parse_args()
    port = args.port
    ballot = Ballot(port)
    blocchain = Blocchain(ballot.public_key, port)
    app.run(host='0.0.0.0', port=port)
