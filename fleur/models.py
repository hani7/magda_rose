# fleur/models.py
from django.db import models
from django.urls import reverse

# fleur/models.py
from django.db import models

# ... your existing models (Category, Product, Order, Payment, etc.) ...

class HomeContent(models.Model):
    title = models.CharField(max_length=180, default="Bienvenue")
    subtitle = models.CharField(max_length=255, blank=True)
    # Upload a video file OR provide a URL (YouTube/Vimeo/direct MP4)
    video_file = models.FileField(upload_to="videos/", blank=True, null=True)
    video_url = models.URLField(blank=True, help_text="YouTube/Vimeo/MP4 URL")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Contenu d’accueil"
        verbose_name_plural = "Contenu d’accueil"

    def __str__(self):
        return "Contenu d’accueil"

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        return obj or cls.objects.create()

    def best_video_src(self):
        if self.video_file:
            return self.video_file.url
        return self.video_url or ""

    def youtube_embed_url(self):
        url = (self.video_url or "").strip()
        if "youtube.com/watch" in url:
            from urllib.parse import urlparse, parse_qs
            vid = parse_qs(urlparse(url).query).get("v", [""])[0]
            if vid:
                return f"https://www.youtube.com/embed/{vid}"
        if "youtu.be/" in url:
            vid = url.split("youtu.be/")[-1].split("?")[0]
            if vid:
                return f"https://www.youtube.com/embed/{vid}"
        return ""


class Category(models.Model):
    name = models.CharField("Nom", max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    class Meta: ordering = ["name"]
    def __str__(self): return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField("Nom", max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    description = models.TextField(blank=True)
    price = models.DecimalField("Prix (DA)", max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    class Meta: ordering = ["name"]
    def __str__(self): return self.name
    def get_buy_url(self): return reverse("fleur:buy_now", args=[self.slug])

class Slot(models.Model):
    # Example codes: 1..12 or A1..A12 — choose what you prefer
    code = models.CharField(max_length=8, unique=True)  # e.g. "1", "2", ... "12" or "A1"
    product = models.ForeignKey(
        Product, null=True, blank=True, on_delete=models.SET_NULL, related_name="slots"
    )
    quantity = models.PositiveIntegerField(default=0)  # how many bouquets currently in this slot
    is_enabled = models.BooleanField(default=True)
    relay_channel = models.PositiveIntegerField(default=1)  # 1..12

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"Slot {self.code}"

    @property
    def available(self):
        return self.is_enabled and self.product and self.product.is_active and self.quantity > 0
   

class OrderStatus(models.TextChoices):
    PENDING_PAYMENT = "En attente paiement", "En attente paiement"
    PAID = "Payée", "Payée"
    FAILED = "Échouée", "Échouée"

class Order(models.Model):
    product = models.ForeignKey("fleur.Product", on_delete=models.PROTECT, related_name="orders")
    slot = models.ForeignKey("fleur.Slot", null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # NOT NULL
    quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, default="NEW")
    vended = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"Order #{self.pk} - {self.product.name} - {self.status}"


class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", "En attente"
    SUCCEEDED = "SUCCEEDED", "Réussi"
    FAILED = "FAILED", "Échoué"


class Payment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="payment")
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    amount_inserted = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=12, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    def remaining(self):
        return max(self.amount_due - self.amount_inserted, 0)
    def change(self):
        extra = self.amount_inserted - self.amount_due
        return extra if extra > 0 else 0
    def __str__(self):
        return f"Payment #{self.pk} for Order #{self.order_id} - {self.status}"
    
