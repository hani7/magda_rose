# fleur/forms.py
from django import forms
from .models import Product, Category,Slot
from .models import HomeContent

class InsertMoneyForm(forms.Form):
    amount = forms.DecimalField(
        label="Montant inséré (DA)",
        min_value=0.0,
        decimal_places=2,
        max_digits=10
    )

class SlotForm(forms.ModelForm):
    class Meta:
        model = Slot
        fields = ["code", "product", "quantity", "is_enabled"]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control", "placeholder": "1 .. 12 ou A1..A12"}),
            "product": forms.Select(attrs={"class": "form-control"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["category", "name", "slug", "image", "description", "price", "is_active"]

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "slug"]


class HomeContentForm(forms.ModelForm):
    class Meta:
        model = HomeContent
        fields = ["title", "subtitle", "video_file", "video_url"]
        help_texts = {
            "video_file": "MP4/WebM recommandé. L’emporte sur l’URL si fourni.",
            "video_url": "YouTube/Vimeo/MP4 direct (si aucun fichier uploadé).",
        }        