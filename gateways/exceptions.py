class GatewayException(Exception):
    """
    Base Exception to be sub-classed by specific gateway implementations.
    """
    pass


class GatewayRetryException(GatewayException):
    """
    Base Exception to be raised when transient errors occur communicating with
    gateways. Should be sub-classed by specific gateway implementations.
    """
    pass
