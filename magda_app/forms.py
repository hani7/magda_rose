# magda_app/forms.py
from django import forms
from django.core.exceptions import ValidationError
from .models import Product

MAX_IMAGE_MB = 5
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "category", "price", "image", "is_active", "featured"]

    def clean_price(self):
        price = self.cleaned_data["price"]
        if price < 0:
            raise ValidationError("Price must be ≥ 0.")
        return price

    def clean_image(self):
        img = self.cleaned_data.get("image")
        if not img:
            return img
        if hasattr(img, "content_type") and img.content_type not in ALLOWED_TYPES:
            raise ValidationError("Only JPEG, PNG, or WebP images are allowed.")
        if img.size > MAX_IMAGE_MB * 1024 * 1024:
            raise ValidationError(f"Image must be ≤ {MAX_IMAGE_MB} MB.")
        return img
