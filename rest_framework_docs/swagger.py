from docs import DocumentationGenerator
from docs import parse_docstring
import jsonpickle
from collections import defaultdict
from django.http import Http404
from django.utils.decorators import classonlymethod
from rest_framework.views import APIView
import re

class Api(object):
    def __init__(self, path="", description="", methods = [], docstring=None, view=None, url_parameters=None):
        self.path = path
        self.children = []
        self.description = description
        self.view = view
        self.methods = methods
        self.docstring = docstring
        self.operations = []
        self.url_parameters = url_parameters

        self.model = self.__map_model()

        #do this after all is set!
        self.__create_operations()

    def get_child(self, path):
        try:
            return [child for child in self.children if child.path == path][0]
        except IndexError:
            return None

    def add_child(self, child):
        self.children.append(child)

    def as_dict(self, docs_path):
        if self.docstring:
            description = self.docstring["description"]
        else:
            description = self.description

        operations = [operation.as_dict() for operation in self.operations]
        return {"path": docs_path + self.path, "description": description, "operations": operations}

    def __create_operations(self):
        self.operations = []
        for method in self.methods:
            if method != "OPTIONS":
                self.operations.append(self.__create_operation(method))

    def __create_operation(self, method):

        doc = self.__parse_doc_for_method(method)

        summary = None
        if doc and doc["description"]:
            summary = doc["description"]

        model = self.__get_model()

        is_list = False
        model_type= None
        if model:
            model_type = model.__name__
            try:
                if self.view.list:
                    is_list = True
                    model_type = "Array[" + model_type + "]"
            except AttributeError:
                pass

        response_class = None
        if method == "GET" and model_type:
            response_class = model_type

        operation = SwaggerOperationObject(
            method = method,
            response_class = response_class,
            summary = summary
        )

        if model_type and method in ["POST", "PUT"]:
            parameter = SwaggerParameter(
                data_type=model_type,
                name=model_type,
                allow_multiple=is_list
            )
            operation.add_parameter(parameter)

        #add params from url TODO: infer type
        if self.url_parameters:
            for key in self.url_parameters.keys():
                operation.add_parameter(SwaggerParameter(param_type="path", data_type="int", allow_multiple=False, name = key))

        #add params from docstring
        if doc["params"]:
            for param in doc["params"]:
                parameter = self.__map_param_from_doc(param)
                if parameter:
                    operation.add_parameter(parameter)

        return operation

    def __map_model(self):
        print "map model"
        try:
            model = self.view.model
            properties = {}
            for field in model._meta.fields:
                properties[field.name] = {"type": map_django_model(field.get_internal_type())}

            return {"id": model.__name__, "properties": properties}

        except Exception, e:
            print e
            return None

    def __map_param_from_doc(self, param):
        try:
            name = param[0]
            attrs = param[1].split(",")
            param_type = attrs[0].strip()
            type = attrs[1].strip()
            description = attrs[2].strip()
            required = True
            try:
                required_text = attrs[3]
                if required_text.strip() == "optional":
                    required = False
            except IndexError:
                pass
            return SwaggerParameter(
                param_type=param_type,
                data_type=type,
                allow_multiple=False,
                required=required,
                name=name,
                description=description
            )
        except IndexError:
            return None


    def __get_model(self):
        try:
            return self.view.model
        except AttributeError:
            return None

    def __parse_doc_for_method(self, method):
        docstring = getattr(self.view, method.lower()).__doc__
        if docstring:
            return parse_docstring(docstring)

        split_lines = self.docstring["description"].split('\n')

        doc = ""
        description = ""
        for line in split_lines:
            if line.startswith(method + ":"):
                doc = line.replace(method + ": ", "")
            else:
                description += line + "\n"
        self.docstring["description"] = description.rstrip('\n')
        return {"description": doc, "params": None}

class SwaggerParameter(object):

    def __init__(self, data_type=None, allow_multiple=False, required=True, param_type="body", name="data", description=""):
        self.data_type = data_type
        self.allow_multiple = allow_multiple
        self.required = required
        self.param_type = param_type
        self.name = name
        self.description = description

    def as_dict(self):
        return {
            "dataType": self.data_type,
            "allowMultiple": self.allow_multiple,
            "required": self.required,
            "paramType": self.param_type,
            "name": self.name,
            "description": self.description
        }

class SwaggerOperationObject(object):

    def __init__(self, method="GET", response_class=None, summary=None):
        self.method = method
        self.nickname = method
        self.response_class = response_class
        self.summary = summary
        self.parameters = []

    def add_parameter(self, parameter):
        self.parameters.append(parameter)

    def as_dict(self):
        return {
            "httpMethod": self.method,
            "nickname": self.method,
            "responseClass": self.response_class,
            "summary": self.summary,
            "parameters": [param.as_dict() for param in self.parameters]
        }

class SwaggerResponseWrapper(object):

    def __init__(self, base_path="", api_version="", apis=None, docs_path="/"):
        self.base_path = base_path
        self.api_version = api_version
        self.apis = apis
        self.docs_path = docs_path

    def as_dict(self):

        dict = {
            "apiVersion": self.api_version,
            "swaggerVersion": "1.1",
            "basePath": self.base_path
        }

        if self.apis:
            dict["apis"] = [api.as_dict(docs_path=self.docs_path) for api in self.apis]
        models = {}
        for api in self.apis:
            if api.model:
                models[api.model["id"]] = api.model

        dict["models"] = models
        return dict

class SwaggerDocumentationGenerator(DocumentationGenerator):


    def __init__(self, urlpatterns=None, base_path="", server_url="", docs_path=""):
        self.urlpatterns = urlpatterns
        self.base_path = base_path
        self.server_url = server_url
        self.docs_path = docs_path
        self.base_api = self.generate_apis()

    def get_docs(self, path=None):
        if path:
            child = self.base_api.get_child(path)
            if not child:
                raise Http404
            children = child.children
            docs_path = "/" + path + "/"
        else:
            docs_path = self.docs_path
            children = self.base_api.children

        response = SwaggerResponseWrapper(
            base_path = self.server_url + "/" + self.base_path,
            api_version = "2.0",
            apis = children,
            docs_path = docs_path
        )

        return jsonpickle.encode(response.as_dict(), unpicklable=False)


    def generate_apis(self):

        base_api = Api(path="/")
        for endpoint in self.urlpatterns:
            if endpoint.callback:
                path =  self.__get_path__(endpoint)
                sub = ""
                if "/" in path:
                    split = path.split("/", 1)
                    path = split[0]
                    sub = split[1]

                child = base_api.get_child(path)
                if not child:
                    child = Api(path=path)
                    base_api.add_child(child)

                regex = re.compile(endpoint.regex.pattern)
                url_params = regex.groupindex

                api = Api(
                    path = sub,
                    methods = self.__get_allowed_methods__(endpoint),
                    docstring = self.__parse_docstring__(endpoint),
                    view=endpoint.callback.cls_instance,
                    url_parameters = url_params
                )

                child.add_child(api)
        return base_api

#TODO: get this from somewhere more robust
def map_django_model(django_model):
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