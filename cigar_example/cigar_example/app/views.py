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




extra_models = {"User": {"id": "User", "properties": {"id": {"type": "int"}}}, "Revision": {"id": "Revision", "properties": {"id": {"type": "int"}, "comment": {"type": "string"}, "process_record": {"type": "int"}, "date": {"type": "string"}, "user": {"type": "User"}}}}
model_wrapper = {"data": {"type": "MODEL"}, "revision": {"type": "Revision"}}

doc_generator = SwaggerDocumentationGenerator(
    urlpatterns=urls.urlpatterns,
    base_path="api/v2/",
    server_url="http://143.97.90.77:8000",
    docs_path="/swagger/",
    model_wrapper=model_wrapper,
    extra_models=extra_models
    )

class SwaggerApiDocumentation(APIView):
    """
    Gets the documentation for the API endpoints
    """
    def get(self, request, match=None, *args, **kwargs):
        docs = doc_generator.get_docs(match)
        return Response(json.loads(docs))