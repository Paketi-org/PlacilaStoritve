import grpc
from concurrent import futures
import time
import unary_pb2_grpc as pb2_grpc
import unary_pb2 as pb2


class UnaryService(pb2_grpc.convertToCryptoServicer):

    def __init__(self, *args, **kwargs):
        pass

    def convertToBitcoin(self, request, context):

        # get the string from the incoming request
        eur = request.message
        bitcoin = str(0.000024 * float(eur))
        result = f'I received {eur} eurs and converted it to {bitcoin} bitcoins'
        result = {'message': result, 'received': True}

        return pb2.MessageResponse(**result)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_convertToCryptoServicer_to_server(UnaryService(), server)
    server.add_insecure_port('[::]:50051')
    print("Starting GRPC server")
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    serve()
