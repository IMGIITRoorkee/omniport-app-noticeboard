from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response

class HelloWorld(APIView):
    """
    This view greets visitors with a friendly 'Hello World!'
    """

    @staticmethod
    def hello_world():
        """
        Return a 'Hello World!' message in JSON format
        :return: a 'Hello World!' message in JSON format
        """

        response = {
            'message': 'Hello World!',
        }
        return Response(response)

    @staticmethod
    def get(_, *__, **___):
        """
        Return a 'Hello World!' message in JSON format
        :param _: the request for which response is being sent
        :param __: additional arguments
        :param ___: additional keyword arguments
        :return: a 'Hello World!' message in JSON format
        """

        return HelloWorld.hello_world()
