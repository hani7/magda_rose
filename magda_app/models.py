# magda_app/models.py
from django.db import models
from django.utils import timezone

class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    class Meta: ordering = ["name"]
    def __str__(self): return self.name

class Product(models.Model):
    name = models.CharField(max_length=120)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="products/")
    is_active = models.BooleanField(default=True)
    featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta: ordering = ["-featured", "-created_at"]
    def __str__(self): return self.name

class OrderIntent(models.Model):
    product = models.ForeignKey("Product", on_delete=models.CASCADE, related_name="order_intents")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"OrderIntent({self.product.name})"