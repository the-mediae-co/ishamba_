from ..exceptions import GatewayException, GatewayRetryException


class AfricasTalkingGatewayException(GatewayException):
    pass


class AfricasTalkingGatewayRetryException(GatewayRetryException):
    """
    Raised when there is a transient error communicating with the
    AfricasTalking gateway and it's safe to retry the communication.
    """
    pass
