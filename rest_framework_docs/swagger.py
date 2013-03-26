from docs import DocumentationGenerator
import jsonpickle
from collections import defaultdict
from django.http import Http404
from django.utils.decorators import classonlymethod
from rest_framework.views import APIView

class SwaggerDocumentationGenerator(DocumentationGenerator):


    def __init__(self, urlpatterns=None, base_path="", server_url="", docs_path=""):
        self.urlpatterns = urlpatterns
        self.base_path = base_path
        self.server_url = server_url
        self.docs_path = docs_path
        self.apis = self.__process_urlpatterns()

    def get_docs(self):

        apis = [{"path": self.docs_path + api, "description":""} for api in self.apis]

        base = self.__create_base_response()
        base["apis"] = apis

        return jsonpickle.encode(base, unpicklable=False)

    def get_apis(self, path):

        if path in self.apis:
            response = self.__create_base_response()
            response["apis"] = [x.as_dict() for x in self.apis[path]]

            models = {}
            for api in response["apis"]:
                api_models = api["models"]
                del api["models"]
                for key, model in api_models.iteritems():
                    if not key in models:
                        models[key] = model
            response["models"] = models

            return jsonpickle.encode(response, unpicklable=False)

        raise Http404

    def __create_base_response(self):
        return {
            "apiVersion": "1.0",
            "swaggerVersion": "1.1",
            "basePath": self.server_url + "/api/v2/" ,
            "apis": []
        }

    def __process_urlpatterns(self):
        """ Assembles ApiDocObject """

        base_apis = defaultdict(list)
        for endpoint in self.urlpatterns:
            base_path = self.__get_path__(endpoint).split("/")[0]
            base_apis[base_path].append(self.__create_apis(endpoint, base_path))

        return base_apis

    def __create_apis(self, endpoint, base_path):
        if not endpoint.callback:
            return None

        path = self.__get_path__(endpoint)
        sub =  path.replace(base_path, "")
        if not sub.startswith("/"):
            sub = "/" + sub

        models = {}
        try:
            model = endpoint.callback.cls_instance.model
            models[model.__name__] = self.__map_model(model)
        except AttributeError:
            model = None

        doc = self.ApiSwaggerDocObject()
        doc.path = sub
        parsed_docstring = self.__parse_docstring__(endpoint)
        doc.params = parsed_docstring['params']
        doc.model = model
        doc.operations = self.__create_operations(endpoint, path, model)
        doc.description = parsed_docstring['description']
        doc.allowed_methods = self.__get_allowed_methods__(endpoint)
        doc.fields = self.__get_serializer_fields__(endpoint)
        doc.models = models
        return doc

    def __create_operations(self, endpoint, sub, model):
        allowed_methods = self.__get_allowed_methods__(endpoint)
        parsed_docstring = self.__parse_docstring__(endpoint)

        list = False
        try:
            list = endpoint.callback.cls_instance.list
        except AttributeError:
            pass

        operations = []
        for method in allowed_methods:
            operation = self.SwaggerApiOperation()
            operation.method = method
            operation.summary = self.__get_summary(parsed_docstring, endpoint, method)
            operation.nickname = method
            operation.is_list = list
            operation.model = model
            operations.append(operation)
        return operations

    def __map_model(self, model):

        properties = {}
        for field in model._meta.fields:
            properties[field.name] = {"type": self.__map_django_model(field.get_internal_type())}

        return {"id": model.__name__, "properties": properties}

    def __map_django_model(self, django_model):
        mappings = {
            "AutoField": "int",
            "CharField": "string",
            "IntegerField": "int",
            "DecimalField": "double",
            "TextField": "string",
            "ForeignKey": "int",
            "BooleanField": "boolean"
        }
        if django_model in mappings:
            return mappings[django_model]
        return None


    def __get_summary(self, parsed_docstring, endpoint, method):

        if method in parsed_docstring["methods"]:
            return parsed_docstring["methods"][method]

        method_doc = self.__get_operation_docstring(endpoint, method)
        if method_doc and method_doc['description'] != "":
            return method_doc['description']

        return parsed_docstring['description']


    def __get_operation_docstring(self, endpoint, method):
        try:
            docstring = endpoint.callback.get_doc_for_method(method)
            description = self._trim(docstring)
            split_lines = description.split('\n')
            trimmed = False  # Flag if string needs to be trimmed
            _params = []

            for line in split_lines:
                if not trimmed:
                    needle = line.find('--')
                    if needle != -1:
                        trim_at = description.find(line)
                        description = description[:trim_at]
                        trimmed = True

                params = line.split(' -- ')
                if len(params) == 2:
                    _params.append([params[0].strip(), params[1].strip()])

            return {'description': description, 'params': _params}
        except AttributeError, e:
            return None


    class ApiSwaggerDocObject(object):
        """ API Documentation Object """
        path = None
        title = None
        description = None
        params = []
        operations = []
        models = None

        def as_dict(self):
            return {"path": self.path, "description": self.description, "models": self.models, "operations": [operation.as_dict() for operation in self.operations if operation.method != "OPTIONS"]}

    class SwaggerApiOperation(object):
        method = None
        summary = None
        response_class = None
        nickname = None
        parameters = []
        model = None

        def as_dict(self):

            return {"httpMethod": self.method, "summary": self.summary, "nickname": self.nickname, "responseClass": self.get_response_class()}

        def get_parameters(self):
            return self.parameters

        def get_response_class(self):
            if self.method != "GET":
                return None
            try:
                response_class =  self.model.__name__
                if self.is_list:
                    response_class = "Array[" + response_class + "]"
                return response_class
            except AttributeError:
                return None


class ApiViewWithDoc(APIView):
    @classonlymethod
    def as_view(cls, **initkwargs):
        self = cls(**initkwargs)
        view = super(ApiViewWithDoc, cls).as_view(**initkwargs)
        view.get_doc_for_method = self.get_doc_for_method
        return view

    def get_doc_for_method(self, method):
        return getattr(self, method.lower()).__doc__