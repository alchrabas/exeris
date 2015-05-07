import pickle


def call(function_to_call):
    if type(function_to_call) is bytes:
        function_to_call = pickle.loads(function_to_call)

    if type(function_to_call) is tuple:

        function = function_to_call[0]
        args = [call_or_pass(arg) for arg in function_to_call[1:]]
        return function(*args)

    raise AssertionError("%s cannot be called as a deferred function".format(str(function_to_call)))


def dumps(function_call):
    return pickle.dumps(function_call)

def call_or_pass(args):
    """
    Tries to call the args if it's a tuple (assuming it's serialized function)
    or passes it unchanged otherwise (assuming it's a normal function argument)
    """
    if args is tuple:
        return call(args)
    else:
        return args