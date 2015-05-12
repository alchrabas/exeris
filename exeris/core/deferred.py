import base64
import pickle


def call(function_to_call):
    if type(function_to_call) is str:
        function_to_call = pickle.loads(base64.decodebytes(function_to_call.encode("ascii")))

    if type(function_to_call) is tuple:

        function = function_to_call[0]
        args = [_call_or_pass(arg) for arg in function_to_call[1:]]

        return function(*args)

    raise AssertionError("%s cannot be called as a deferred function".format(str(function_to_call)))


def dumps(function_call):
    return base64.encodebytes(pickle.dumps(function_call)).decode("ascii")


def _call_or_pass(arg):
    """
    Tries to call the args if it's a tuple (assuming it's serialized function)
    or passes it unchanged otherwise (assuming it's a normal function argument)
    """
    if type(arg) is tuple:
        return call(arg)
    else:
        return arg
