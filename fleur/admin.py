# fleur/admin.py
from django.contrib import admin
from .models import Category, Product, Order, Payment, OrderStatus, PaymentStatus,Slot
from .models import HomeContent


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
    autocomplete_fields = ("category",)

@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin):
    list_display = ("code", "product", "quantity", "is_enabled")
    list_editable = ("product", "quantity", "is_enabled")
    search_fields = ("code",)
    list_filter = ("is_enabled", "product")

class PaymentInline(admin.StackedInline):
    model = Payment
    can_delete = False
    extra = 0
    readonly_fields = ("created_at",)
    fieldsets = (
        ("Paiement", {
            "fields": (
                ("amount_due", "amount_inserted"),
                "status",
                "created_at",
            )
        }),
    )

class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "slot", "status", "vended", "created_at")
    list_filter = ("status", "vended")
    search_fields = ("id", "product__name", "slot__code")
    
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "unit_price", "status", "created_at")
    list_filter = ("status", "product")
    search_fields = ("id", "product__name")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
    autocomplete_fields = ("product",)
    inlines = [PaymentInline]

    actions = ["mark_paid", "mark_failed"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("product")

    def mark_paid(self, request, queryset):
        updated = 0
        for order in queryset:
            if hasattr(order, "payment"):
                order.payment.status = PaymentStatus.SUCCEEDED
                order.payment.amount_inserted = order.payment.amount_due
                order.payment.save(update_fields=["status", "amount_inserted"])
            order.status = OrderStatus.PAID
            order.save(update_fields=["status"])
            updated += 1
        self.message_user(request, f"{updated} commande(s) marquées payées.")
    mark_paid.short_description = "Marquer comme payée"

    def mark_failed(self, request, queryset):
        updated = 0
        for order in queryset:
            if hasattr(order, "payment"):
                order.payment.status = PaymentStatus.FAILED
                order.payment.save(update_fields=["status"])
            order.status = OrderStatus.FAILED
            order.save(update_fields=["status"])
            updated += 1
        self.message_user(request, f"{updated} commande(s) marquées échouées.")
    mark_failed.short_description = "Marquer comme échouée"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "amount_due", "amount_inserted", "remaining_display", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("id", "order__id", "order__product__name")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
    autocomplete_fields = ("order",)

    def remaining_display(self, obj):
        return obj.remaining()
    remaining_display.short_description = "Reste à payer (DA)"
