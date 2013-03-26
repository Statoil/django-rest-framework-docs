from rest_framework.views import Response, APIView
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from cigar_example.app.models import Cigar, Manufacturer, Countries
from serializers import CigarSerializer, ManufacturerSerializer, CountrySerializer

class CigarList(ListCreateAPIView):
    """
    Lists and creates cigars from the database.
    """

    model = Cigar
    """ This is the model """
    serializer_class = CigarSerializer


class CigarDetails(RetrieveUpdateDestroyAPIView):
    """
    Gets a detailed view of an individual cigar record. Can be updated and deleted. Each cigar must
    be assigned to a manufacturer
    """
    model = Cigar
    serializer_class = CigarSerializer


class ManufacturerList(ListCreateAPIView):
    """
    Gets the list of cigar manufacturers from the database.

    GET: This is the description for GET on ManufacturerList
    POST: This is the description for Post on ManufacturerList

    """
    list = True
    model = Manufacturer
    serializer_class = ManufacturerSerializer

class ManufacturerDetails(RetrieveUpdateDestroyAPIView):
    """
    Returns the details on a manufacturer

    GET: This is the description for get on ManufacturerDetail
    PUT: This is the description for put on ManufacturerDetail
    PATCH: This is the description for put on ManufacturerDetail
    DELETE: This is the description for delete on ManufacturerDetail

    """
    model = Manufacturer
    serializer_class = ManufacturerSerializer

class CountryList(ListCreateAPIView):
    """
    Gets a list of countries. Allows the creation of a new country.

    GET: Gets a list of countries.
    POST: Allows the creation of a new country.

    """
    model = Countries
    serializer_class = CountrySerializer

class CountryDetails(RetrieveUpdateDestroyAPIView):
    """
    Detailed view of the country
    """
    model = Countries
    serializer_class = CountrySerializer


class MyCustomView(APIView):
    """
    This is a custom view that can be anything at all. It's not using a serializer class,
    but I can define my own parameters like so!

    horse -- the name of your horse

    """

    def get(self, *args, **kwargs):
        return Response({'foo':'bar'})

    def post(self, *args, **kwargs):
        pass

class MyCustomViewGet(APIView):
    """
    This is a custom view that can be anything at all. It's not using a serializer class,
    but I can define my own parameters like so!

    horse -- the name of your horse

    """

    model = Countries

    def get(self, *args, **kwargs):
        """
        Doc for custom things

        my_param2 -- path, String, desc
        my_param -- query, Int, desc, optional

        """
        return Response({'foo':'bar'})


class MyCustomViewPost(APIView):
    """
    This is a custom view that can be anything at all.
    """

    def post(self, *args, **kwargs):
        pass