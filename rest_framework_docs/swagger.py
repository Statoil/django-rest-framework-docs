from docs import DocumentationGenerator
from docs import parse_docstring
import jsonpickle
from collections import defaultdict
from django.http import Http404
from django.utils.decorators import classonlymethod
from rest_framework.views import APIView
from copy import deepcopy
import re

class Api(object):
    def __init__(self, path="", description="", methods = [], docstring=None, view=None, url_parameters=None, model_wrapper=None):
        self.path = path
        self.children = []
        self.description = description
        self.view = view
        self.methods = methods
        self.docstring = docstring
        self.operations = []
        self.url_parameters = url_parameters
        self.model_wrapper = model_wrapper
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

        operations = [operation.as_dict(model_wrapper=self.model_wrapper) for operation in self.operations]
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
            except AttributeError:
                pass

        response_class = None
        if method == "GET" and model_type:
            response_class = model_type

        operation = SwaggerOperationObject(
            method = method,
            response_class = response_class,
            summary = summary,
            is_list=is_list
        )

        #automagically set model as body param for POST and PUT
        if model_type and method in ["POST", "PUT"]:
            if self.model_wrapper:
                model_type = wrap_model_type(model_type, is_list)

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
        try:
            model = self.view.model
            properties = {}
            for field in model._meta.fields:
                properties[field.name] = {"type": map_django_model(field.get_internal_type())}
            return {"id": model.__name__, "properties": properties}
        except Exception, e:
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

    def __init__(self, method="GET", response_class=None, summary=None, is_list=False):
        self.method = method
        self.nickname = method
        self.response_class = response_class
        self.summary = summary
        self.parameters = []
        self.is_list = is_list

    def add_parameter(self, parameter):
        self.parameters.append(parameter)

    def as_dict(self, model_wrapper=None):
        response_class = self.response_class

        if self.response_class:
            if model_wrapper:
                response_class = wrap_model_type(self.response_class, self.is_list)
            else:
                if self.is_list:
                    response_class = "Array[" + self.response_class + "]"
                else:
                    response_class = self.response_class

        return {
            "httpMethod": self.method,
            "nickname": self.method,
            "responseClass": response_class,
            "summary": self.summary,
            "parameters": [param.as_dict() for param in self.parameters]
        }

class SwaggerResponseWrapper(object):

    def __init__(self, base_path="", api_version="", apis=None, docs_path="/", model_wrapper=None, extra_models=None):
        self.base_path = base_path
        self.api_version = api_version
        self.apis = apis
        self.docs_path = docs_path
        self.model_wrapper = model_wrapper
        self.extra_models = extra_models

    def as_dict(self):

        response_dict = {
            "apiVersion": self.api_version,
            "swaggerVersion": "1.1",
            "basePath": self.base_path
        }

        if self.apis:
            response_dict["apis"] = [api.as_dict(docs_path=self.docs_path) for api in self.apis]
        models = {}
        for api in self.apis:
            if api.model:
                models[api.model["id"]] = api.model
                if self.model_wrapper:
                    wrapper_copy = deepcopy(self.model_wrapper)
                    wrapper_name = api.model["id"] + "Wrapper"
                    wrapper_copy["data"]["type"] = api.model["id"]
                    models[wrapper_name] = {"id": wrapper_name, "properties": wrapper_copy}

                    wrapper_list_copy = deepcopy(self.model_wrapper)
                    list_wrapper_name = api.model["id"] + "ListWrapper"
                    wrapper_list_copy["data"]["type"] = "Array"
                    wrapper_list_copy["data"]["items"] = {"$ref": api.model["id"]}
                    models[list_wrapper_name] = {"id": list_wrapper_name, "properties": wrapper_list_copy}

        response_dict["models"] = models
        if self.extra_models:
            response_dict["models"] = dict(self.extra_models.items() + response_dict["models"].items())
        return response_dict

class SwaggerDocumentationGenerator(DocumentationGenerator):

    def __init__(self, urlpatterns=None, base_path="", server_url="", docs_path="", model_wrapper=None, extra_models=None):
        self.urlpatterns = urlpatterns
        self.base_path = base_path
        self.server_url = server_url
        self.docs_path = docs_path

        #extra_models are used if your model_wrapper references any other models
        self.extra_models = extra_models

        #set the model_wrapper to a dict with a swagger representation of the object you want to wrap the model in
        #the data-attribute of the model_wrapper will be set to the model
        self.model_wrapper = model_wrapper
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
            docs_path = docs_path,
            model_wrapper = self.model_wrapper,
            extra_models = self.extra_models
        )

        return jsonpickle.encode(response.as_dict(), unpicklable=False)


    def generate_api(self, base_api, path, endpoint, sub, use_wrapper=True, exclude_param=None):

        child = base_api.get_child(path)
        if not child:
            child = Api(path=path)
            base_api.add_child(child)

        regex = re.compile(endpoint.regex.pattern)
        url_params = regex.groupindex
        if exclude_param and exclude_param in url_params:
            del url_params[exclude_param]

        if use_wrapper:
            model_wrapper = self.model_wrapper
        else:
            model_wrapper = None

        api = Api(
            path = sub,
            methods = self.__get_allowed_methods__(endpoint),
            docstring = self.__parse_docstring__(endpoint),
            view=endpoint.callback.cls_instance,
            url_parameters = url_params,
            model_wrapper = model_wrapper
        )

        child.add_child(api)

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

                use_wrapper = True
                if hasattr(endpoint.callback.cls_instance, "wrapper"):
                    if endpoint.callback.cls_instance.wrapper is False:
                        use_wrapper = False

                #handle substitutions
                if hasattr(endpoint.callback.cls_instance, 'param_mappings'):
                    for key, value in endpoint.callback.cls_instance.param_mappings.iteritems():
                        parameter = "{"+ key + "}"
                        if parameter in path:
                            for substitute in value:
                                p = path.replace(parameter, substitute)
                                self.generate_api(base_api, p, endpoint, sub, use_wrapper=use_wrapper, exclude_param=key)
                else:
                    self.generate_api(base_api, path, endpoint, sub, use_wrapper=use_wrapper)

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
        "BooleanField": "boolean",
        "PositiveIntegerField": "int",
        "DateTimeField": "Date"
    }
    if django_model in mappings:
        return mappings[django_model]
    return None


def wrap_model_type(model_type, is_list):
    if is_list:
        return model_type + "ListWrapper"
    else:
        return model_type + "Wrapper"