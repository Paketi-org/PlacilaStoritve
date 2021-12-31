import grpc
import unary_pb2_grpc as pb2_grpc
import unary_pb2 as pb2


class UnaryClient(object):
    """
    Client for gRPC functionality
    """

    def __init__(self):
        self.host = 'localhost'
        self.server_port = 50051

        # instantiate a channel
        self.channel = grpc.insecure_channel(
            '{}:{}'.format(self.host, self.server_port))

        # bind the client and the server
        self.stub = pb2_grpc.convertToCryptoStub(self.channel)

    def get_bitcoins(self, eur):
        """
        Client function to call the rpc for GetServerResponse
        """
        message = pb2.Message(message=eur)
        print(f'Sent request to convert {message} to bitcoins')
        return self.stub.convertToBitcoin(message)


if __name__ == '__main__':
    client = UnaryClient()
    result = client.get_bitcoins("10.00")
    print(f'Received from server {result}')
