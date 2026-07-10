from django import forms

class AdministrativeLevelSelectWidget(forms.CheckboxSelectMultiple):
    def render(self, name, value, attrs=None, renderer=None):
        output = super().render(name, value, attrs, renderer)
        return output.replace("&nbsp;", "")
