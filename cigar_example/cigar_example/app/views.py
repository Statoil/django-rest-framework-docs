import json
from rest_framework.response import Response
from rest_framework.views import APIView
from cigar_example.restapi import urls
from rest_framework_docs.docs import DocumentationGenerator
from rest_framework_docs.swagger import SwaggerDocumentationGenerator

class ApiDocumentation(APIView):
    """
    Gets the documentation for the API endpoints
    """
    def get(self, *args, **kwargs):
        docs = DocumentationGenerator(urls.urlpatterns).get_docs()
        return Response(json.loads(docs))


doc_generator = SwaggerDocumentationGenerator(urls.urlpatterns, "api/v2/", "http://143.97.90.77:8000", "/swagger/")

class SwaggerApiDocumentation(APIView):
    """
    Gets the documentation for the API endpoints
    """
    def get(self, request, match=None, *args, **kwargs):
        if match:
            docs = doc_generator.get_apis(match)
        else:
            docs = doc_generator.get_docs()
        return Response(json.loads(docs))