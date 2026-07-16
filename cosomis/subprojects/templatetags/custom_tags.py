from django import template
from django.utils.translation import gettext_lazy
from subprojects.models import Project, Financier
from datetime import datetime

from cosomis.constants import SUB_PROJECT_STATUS_COLOR, TYPES_OF_SUB_PROJECT_COLOR

register = template.Library()



@register.filter(name="imgAWSS3Filter")
def img_aws_s3_filter(uri):
    return uri.split("?")[0]

@register.filter(name='has_group') 
def has_group(user, group_name):
    return user.groups.filter(name=group_name).exists() 

@register.filter(name='has_in_a_group') 
def has_in_a_group(user):
    return user.groups.all().exists()

@register.filter(name="not_local")
def not_local(uri):
    return uri.split(":")[0] != 'file'

@register.filter(name="is_pdf")
def is_pdf(uri):
    uri = uri.split("?")[0]
    return uri.split(".")[-1] in ['pdf', 'docx', 'doc']

@register.simple_tag
def get_initials(string):
    if not string or string in ('', ):
        return 'N'
    return ''.join((w[0] for w in string.split(' ') if w)).upper()

@register.filter(expects_localtime=True)
def string_to_date(date_time, date_format="%Y-%m-%dT%H:%M:%S.%fZ"):
    if date_time:
        return datetime.strptime(date_time, date_format)
    
@register.filter(name="replace")
def replace(v: str, s: str):
    v = str(v)
    if "r|" in s:
        if len(s.split('r|')) != 2:
            return v
        else:
            what, to = s.split('r|')
            return v.replace(what, to)
    else:
        _ = s.split(";")
        for elt in _:
            v = v.replace(elt, "")
    return v

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
    
    if user.groups.filter(name="Minister").exists():
        return gettext_lazy("Minister").__str__()
    if user.groups.filter(name="Advisor").exists():
        return gettext_lazy("Advisor").__str__()
    if user.groups.filter(name="GeneralManager").exists():
        return gettext_lazy("General Manager").__str__()
    if user.groups.filter(name="NationalCoordinator").exists():
        return gettext_lazy("National Coordinator").__str__()
    if user.groups.filter(name="RegionalCoordinator").exists():
        return gettext_lazy("Regional Coordinator").__str__()
    if user.groups.filter(name="Director").exists():
        return gettext_lazy("Director").__str__()
    
    if user.groups.filter(name="Evaluator").exists():
        return gettext_lazy("Evaluator").__str__()
    if user.groups.filter(name="Financial").exists():
        return gettext_lazy("Financial ").__str__()
    if user.groups.filter(name="ProcurementSpecialist").exists():
        return gettext_lazy("Procurement Specialist").__str__()
    if user.groups.filter(name="KnowledgeManager").exists():
        return gettext_lazy("Knowledge manager").__str__()
    if user.groups.filter(name="CDDSpecialist").exists():
        return gettext_lazy("CDD Specialist").__str__()
    if user.groups.filter(name="Accountant").exists():
        return gettext_lazy("Accountant").__str__()
    if user.groups.filter(name="Infra").exists():
        return gettext_lazy("Infra").__str__()
    
    if user.groups.filter(name="YouthProgramSpecialist").exists():
        return gettext_lazy("Youth Program Specialist").__str__()
    if user.groups.filter(name="LocalEconomicDevelopmentSpecialist").exists():
        return gettext_lazy("Local Economic Development Specialist").__str__()
    if user.groups.filter(name="CommunicationSpecialist").exists():
        return gettext_lazy("Communicating").__str__()
    if user.groups.filter(name="CommunityFacilitator").exists():
        return gettext_lazy("Community Facilitator").__str__()
    if user.groups.filter(name="TechnicalFacilitator").exists():
        return gettext_lazy("Technical Facilitator").__str__()
        
    if user.groups.filter(name="Supervisor").exists():
        return gettext_lazy("Supervisor").__str__()
    
    if user.groups.filter(name="Validator").exists():
        return gettext_lazy("Validator").__str__()


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

class MakeVarNode(template.Node):
    def __init__(self, value, varname):
        self.value = value
        self.varname = varname

    def render(self, context):
        context[self.varname] = None
        if self.value.isdigit():
            context[self.varname] = int(self.value)
        else:
            context[self.varname] = str(self.value).replace('"', '')
        return ""
    
@register.tag
def var(parser, token):
    bits = list(token.split_contents())
    if len(bits) == 4 and bits[-2] == "as":
        varname = bits[-1]
        value = bits[1]
        return MakeVarNode(value, varname)
    else:
        raise template.TemplateSyntaxError("%r expected format is 'item as varname'" % bits[0])

@register.filter(name='get_to_percent_str') 
def get_to_percent_str(number):
    return str(number if number >= 10 else "0"+str(number)) + " %"

@register.filter
def get(dictionary, key):
    if type(dictionary) is not dict:
        return None
    return dictionary.get(key, None)

@register.filter
def get_on_list(data, index):
    try:
        return data[index]
    except:
        return None

@register.filter
def sum(data):
    
    return sum(data)

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

    if value != 0 and (not value or not str(value).replace('-','').replace('.','',1).replace(',','',1).isdigit()):
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

@register.filter
def format_id(value: str):
    return value.replace("&","").replace("(","").replace(")","").replace(".","").replace("'","").replace("\"","").replace(" ","").replace("+","")


@register.simple_tag
def get_days_until_today(date_time):
    date = datetime.strptime(date_time, '%Y-%m-%dT%H:%M:%S.%fZ')
    delta = datetime.now() - date
    return delta.days


@register.filter
def get_facilitator_with_ids(village, project_ids):
    return village.get_facilitator(project_ids)


FINANCIAL_STATUS_BADGE_CLASSES = {
    'PENDING': 'badge-warning',
    'PARTIALLY_VALIDATED': 'badge-warning',
    'PARTIALLY_JUSTIFIED': 'badge-warning',
    'NOT_JUSTIFIED': 'badge-danger',
    'FULLY_VALIDATED': 'badge-success',
    'FULLY_JUSTIFIED': 'badge-success',
    'EXECUTED': 'badge-success',
    'REJECTED': 'badge-danger',
    'CANCELLED': 'badge-danger',
    'ACTIVE': 'badge-success',
    'SUSPENDED': 'badge-warning',
    'ABANDONED': 'badge-danger',
    'CLOSED': 'badge-secondary',
    'FORWARD': 'badge-info',
    'RETURN': 'badge-dark',
    'CREDIT': 'badge-primary',
    'GRANT': 'badge-info',
    'BANK_TRANSFER': 'badge-info',
    'CHEQUE': 'badge-dark',
}

ACCOUNT_TYPE_BADGE_CLASSES = {
    'PROJECT': 'badge-primary',
    'REGIONAL_OFFICE': 'badge-info',
    'TOWN_HALL': 'badge-dark',
    'CVD': 'badge-success',
    'PROJECT_SPECIALIST': 'badge-warning',
    'SERVICE_PROVIDER': 'badge-secondary',
}


@register.filter(name='financial_status_badge')
def financial_status_badge(value):
    """Bootstrap badge class for the financial app's status-like TextChoices values."""
    return FINANCIAL_STATUS_BADGE_CLASSES.get(str(value), 'badge-secondary')


@register.filter(name='account_type_badge')
def account_type_badge(value):
    """Bootstrap badge class per financial.Account.AccountType, fixed per type (never reassigned)."""
    return ACCOUNT_TYPE_BADGE_CLASSES.get(str(value), 'badge-secondary')


@register.simple_tag(takes_context=True)
def querystring_replace(context, **kwargs):
    """Current request's querystring with the given params overridden/removed (value=None
    removes it) - used so pagination links don't drop active filters (project/funding/...)."""
    request = context['request']
    query = request.GET.copy()
    for key, value in kwargs.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = value
    return query.urlencode()