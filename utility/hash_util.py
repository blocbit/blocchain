import hashlib as hl
import json

# __all__ = ['hash_string_256', 'hash_bloc']


def hash_string_256(string):
    """Create a SHA256 hash for a given input string.

    Arguments:
        :string: The string which should be hashed.
    """
    return hl.sha256(string).hexdigest()


def hash_bloc(bloc):
    """Hashes a bloc and returns a string representation of it.

    Arguments:
        :bloc: The bloc that should be hashed.
    """
    hashable_bloc = bloc.__dict__.copy()
    hashable_bloc['submissions'] = [
        tx.to_ordered_dict() for tx in hashable_bloc['submissions']
    ]
    return hash_string_256(json.dumps(hashable_bloc, sort_keys=True).encode())
