from django.contrib.auth import get_user_model

def model_has_field(model_class, field_name):
    try:
        model_class._meta.get_field(field_name)
        return True
    except:
        return False