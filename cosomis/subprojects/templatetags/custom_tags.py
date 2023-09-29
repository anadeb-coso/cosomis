from django import template
from django.utils.translation import gettext_lazy
from subprojects.models import Project, Financier

from cosomis.constants import SUB_PROJECT_STATUS_COLOR, TYPES_OF_SUB_PROJECT_COLOR

register = template.Library()



@register.filter(name="imgAWSS3Filter")
def img_aws_s3_filter(uri):
    return uri.split("?")[0]

@register.filter(name='has_group') 
def has_group(user, group_name):
    return user.groups.filter(name=group_name).exists() 

@register.filter(name='get_group_high') 
def get_group_high(user):
    """
    All Groups permissions
        - SuperAdmin            : 
        - CDD Specialist        : CDDSpecialist
        - Admin                 : Admin
        - Evaluator             : Evaluator
        - Accountant            : Accountant
        - Regional Coordinator  : RegionalCoordinator
        - National Coordinator  : NationalCoordinator
        - General Manager       : GeneralManager
        - Director              : Director
        - Advisor               : Advisor
        - Minister              : Minister
        - Infra                 : Infra
    """
    if user.is_superuser:
        return gettext_lazy("Principal Administrator").__str__()
    
    if user.groups.filter(name="Admin").exists():
        return gettext_lazy("Administrator").__str__()
    if user.groups.filter(name="CDDSpecialist").exists():
        return gettext_lazy("CDD Specialist").__str__()
    if user.groups.filter(name="Evaluator").exists():
        return gettext_lazy("Evaluator").__str__()
    if user.groups.filter(name="Accountant").exists():
        return gettext_lazy("Accountant").__str__()
    if user.groups.filter(name="RegionalCoordinator").exists():
        return gettext_lazy("Regional Coordinator").__str__()
    if user.groups.filter(name="NationalCoordinator").exists():
        return gettext_lazy("National Coordinator").__str__()
    if user.groups.filter(name="GeneralManager").exists():
        return gettext_lazy("General Manager").__str__()
    if user.groups.filter(name="Director").exists():
        return gettext_lazy("Director").__str__()
    if user.groups.filter(name="Advisor").exists():
        return gettext_lazy("Advisor").__str__()
    if user.groups.filter(name="Minister").exists():
        return gettext_lazy("Minister").__str__()
    if user.groups.filter(name="Infra").exists():
        return gettext_lazy("Infra").__str__()


    return gettext_lazy("User").__str__()

class MakeListNode(template.Node):
    def __init__(self, items, varname):
        self.items = items
        self.varname = varname

    def render(self, context):
        context[self.varname] = []
        for i in self.items:
            if i.isdigit():
                context[self.varname].append(int(i))
            else:
                context[self.varname].append(str(i).replace('"', ''))
        return ""
    
@register.tag
def make_list(parser, token):
    bits = list(token.split_contents())
    if len(bits) >= 4 and bits[-2] == "as":
        varname = bits[-1]
        items = bits[1:-2]
        return MakeListNode(items, varname)
    else:
        raise template.TemplateSyntaxError("%r expected format is 'item [item ...] as varname'" % bits[0])
    
@register.filter(name='get_to_percent_str') 
def get_to_percent_str(number):
    return str(number if number >= 10 else "0"+str(number)) + " %"

@register.filter
def get(dictionary, key):
    return dictionary.get(key, None)

@register.filter
def get_on_list(data, index):
    try:
        return data[index]
    except:
        return None

@register.filter
def isnumber(value):
    return str(value).replace('-','').replace('.','',1).replace(',','',1).isdigit()

@register.filter
def get_project_by_id(pk):
    return Project.objects.get(pk=pk)

@register.filter
def get_financier_by_id(pk):
    return Financier.objects.get(pk=pk)

@register.filter
def join_with_commas(obj_list):
    """Takes a list of objects and returns their string representations,
    separated by commas and with 'and' between the penultimate and final items
    For example, for a list of fruit objects:
    [<Fruit: apples>, <Fruit: oranges>, <Fruit: pears>] -> 'apples, oranges and pears'
    """
    if not obj_list:
        return ""
    l=len(obj_list)
    if l==1:
        return u"%s" % obj_list[0]
    else:    
        return ", ".join(str(obj) for obj in obj_list[:l-1]) \
                + " " + gettext_lazy("and").__str__() + " " + str(obj_list[l-1])

@register.filter
def separate_with_space(value, unit=None, show_float=False):
    if unit:
        unit = " " + unit
    else:
        unit = ""
    
    if not show_float and value:
        value = round(float(value))

    if not value or not str(value).replace('-','').replace('.','',1).replace(',','',1).isdigit():
        return ""
    

    float_values = str(value).split(',')
    if len(float_values) > 1:
        float_value = float_values[-1]
    else:
        float_value = float_values[0]
    float_values = str(float_value).split('.')
    if len(float_values) > 1:
        float_value = float_values[-1]
    else:
        float_value = None



    value = str(value).split(',')[0].split('.')[0]
    l = len(str(int(value)))
    if l in (0, 1) and int(value) < 1:
        return str(int(value)) + unit
    
    list_value_str = list(value)
    list_value_str.reverse()
    money_format = ""
    for i in range(1, len(list_value_str)+1):
        money_format += list_value_str[i-1]
        if i%3 == 0 :
            money_format += " "

    list_money_format = list(money_format)
    list_money_format.reverse()

    return "".join(list_money_format) + "." + float_value + unit if float_value else "".join(list_money_format) + unit


@register.filter
def remove_zeros_on_zeros(value):
    if not value or not str(value).replace('.','',1).replace(',','',1).isdigit():
        return ""
    value = str(value).split(',')[0].split('.')[0]
    l = len(str(int(value)))
    
    if l in (0, 1) and int(value) < 1:
        return int(value)
    
    return value

    
@register.filter
def subtract(value, arg):
    return value - arg

@register.filter(name="checkType")
def check_type(elt, _type):
    return  type(elt).__name__ == _type

@register.filter
def split(value, key):
    return value.split(key)

@register.simple_tag
def call_method(obj, method_name, *args):
    method = getattr(obj, method_name)
    return method(*args)

@register.filter
def get_step_color(key):
    return SUB_PROJECT_STATUS_COLOR.get(key, '#000000')

@register.filter
def get_type_sub_project_color(key):
    return TYPES_OF_SUB_PROJECT_COLOR.get(key, '#00ffff') #Default e-Aqua f-Aqua