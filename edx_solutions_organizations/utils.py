""" Utility methods for Organization Attributes """


def generate_key_for_field(data):
    """
    Method used to generate key for the attribute of organizations
    :param data: existing attributes with keys
    :return: next key to be placed against attribute
    """
    keys = [int(key) for key in data.keys()]
    return max(keys) + 1 if keys else 1


def is_field_exists(name, data):
    """
    Method used to check whether name/field exists for the attribute of organizations
    :param name: name of the attribute
    :param data: existing attributes with keys
    :return: boolean value
    """
    return name in [value for key, value in data.items()]


def is_key_exists(key, data):
    """
    Method used to check whether key exists for the attribute of organizations
    :param key: key of the attribute
    :param data: existing attributes with keys
    :return: boolean value
    """
    return key in data.keys()
