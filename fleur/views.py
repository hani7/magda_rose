# fleur/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
import requests
from .models import Category, Product, Order, OrderStatus, Payment, PaymentStatus
from .forms import InsertMoneyForm, SlotForm
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from .models import Product, Category, Order,Slot
from .forms import ProductForm, CategoryForm
from django.db.models import Q
from .models import HomeContent
from .forms import HomeContentForm
from django.http import JsonResponse
from .forms import InsertMoneyForm  # keep your simple amount form
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponseBadRequest
from django.db import transaction

def mes_bouquets(request):
    # Only show enabled slots with an active product and quantity > 0
    slots = (
        Slot.objects
        .select_related("product")
        .filter(is_enabled=True, product__isnull=False, product__is_active=True, quantity__gt=0)
        .order_by("code")
    )
    return render(request, "fleur/mes_bouquets.html", {"slots": slots})

def home(request):
    content = HomeContent.get_solo()
    ctx = {
        "content": content,
        "embed_url": content.youtube_embed_url(),
        "best_src": content.best_video_src(),
    }
    return render(request, "fleur/home.html", ctx)

def product_list(request, category_slug=None):
    """
    Page publique listant tous les produits actifs.
    - /shop/                   : tous
    - /shop/?q=rose           : recherche
    - /shop/c/<slug>/         : par catégorie
    """
    categories = Category.objects.all().order_by("name")
    products = Product.objects.filter(is_active=True).select_related("category").order_by("name")
    current_category = None

    if category_slug:
        current_category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=current_category)

    q = request.GET.get("q") or ""
    if q:
        products = products.filter(Q(name__icontains=q) | Q(description__icontains=q))

    return render(request, "fleur/product_list.html", {
        "categories": categories,
        "current_category": current_category,
        "products": products,
        "q": q,
    })

def buy_now(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)

    slot = None
    sid = request.GET.get("slot")
    if sid:
        slot = Slot.objects.filter(pk=sid).select_related("product").first()
        if not slot or slot.product_id != product.id or not slot.is_enabled or slot.quantity <= 0:
            messages.error(request, "Ce slot n'est pas disponible pour ce produit.")
            return redirect("fleur:mes_bouquets")

    order = Order.objects.create(
        product=product,
        slot=slot,
        unit_price=product.price,   # <-- IMPORTANT
        quantity=1,                 # <-- if you track qty
        status="NEW",
    )

    payment = Payment.objects.create(
        order=order,
        amount_due=product.price,   # or product.price * order.quantity
        amount_inserted=0,
        status=PaymentStatus.PENDING,
    )
    return redirect("fleur:payment_insert", payment.pk)

@require_http_methods(["GET", "POST"])
def payment_insert(request, pk):
    """
    Payment insert page:
      - UI shows three bill buttons (500/1000/2000) that talk to the local bridge (127.0.0.1:9999/stack).
      - Bridge notifies Django via /api/payment/insert-event/ when a bill is ACTUALLY accepted.
      - This view serves JSON for polling (?json=1) so the UI updates amount_inserted/remaining.
      - POST with 'cancel' marks the order/payment as FAILED and redirects to the failed page.
    """
    payment = get_object_or_404(Payment, pk=pk)
    order = payment.order

    # If already finished, route immediately
    if payment.status == PaymentStatus.SUCCEEDED:
        return redirect("fleur:payment_success", payment.pk)
    if payment.status == PaymentStatus.FAILED:
        return redirect("fleur:payment_failed", payment.pk)

    # Live polling endpoint
    if request.GET.get("json") == "1":
        amount_due = float(payment.amount_due)
        amount_inserted = float(payment.amount_inserted or 0)
        return JsonResponse({
            "amount_due": amount_due,
            "amount_inserted": amount_inserted,
            "remaining": max(0.0, amount_due - amount_inserted),
            "completed": amount_inserted >= amount_due,
            "status": payment.status,
            "payment_id": payment.pk,
            "order_id": order.pk,
        })

    # Cancel flow (annuler)
    if request.method == "POST" and "cancel" in request.POST:
        payment.status = PaymentStatus.FAILED
        order.status = OrderStatus.FAILED
        payment.save(update_fields=["status"])
        order.save(update_fields=["status"])
        messages.warning(request, "Paiement annulé.")
        return redirect("fleur:payment_failed", payment.pk)

    remaining = max(0, (payment.amount_due or 0) - (payment.amount_inserted or 0))
    return render(request, "fleur/payment_insert.html", {
        "payment": payment,
        "order": order,
        "product": order.product,
        "remaining": remaining,
    })

BRIDGE_BASE = "http://127.0.0.1:9999"  # device_bridge_server.py

def payment_success(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    order = payment.order

    if payment.status != PaymentStatus.SUCCEEDED:
        messages.info(request, "Paiement non terminé.")
        return redirect("fleur:payment_insert", payment.pk)

    # If already handled once, just render the page
    if order.vended:
        return render(request, "fleur/payment_success.html",
                      {"payment": payment, "order": order, "product": order.product})

    # Open the physical slot if we have one
    if order.slot_id:
        try:
            slot = Slot.objects.get(pk=order.slot_id)
            channel = slot.relay_channel or 1
            # Call the bridge to open the slot
            r = requests.post(f"{BRIDGE_BASE}/open-slot",
                              json={"channel": int(channel)}, timeout=3)
            r.raise_for_status()
            jr = r.json()
            if not jr.get("ok"):
                messages.warning(request, "Ouverture mécanique non confirmée (bridge).")
        except Exception as e:
            messages.warning(request, f"Bridge indisponible: {e}")

    # Mark as vended and decrement stock exactly once
    with transaction.atomic():
        if not order.vended:
            if order.slot_id:
                slot = Slot.objects.select_for_update().get(pk=order.slot_id)
                if slot.quantity > 0:
                    slot.quantity -= 1
                    slot.save(update_fields=["quantity"])
            order.vended = True
            order.status = "PAID"
            order.save(update_fields=["vended", "status"])

    return render(request, "fleur/payment_success.html",
                  {"payment": payment, "order": order, "product": order.product})

def payment_failed(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    order = payment.order
    # If not failed, send user back to insert page
    if payment.status == PaymentStatus.SUCCEEDED:
        return redirect("fleur:payment_success", payment.pk)
    if payment.status != PaymentStatus.FAILED:
        messages.info(request, "Paiement en cours. Continuez l'insertion.")
        return redirect("fleur:payment_insert", payment.pk)
    return render(request, "fleur/payment_failed.html", {
        "payment": payment,
        "order": order,
        "product": order.product,
    })

# If someone hits "/" in this example, just send them to back-office (change if you have a public shop)
def public_redirect(request):
    return redirect("fleur:bo_dashboard")

@staff_member_required
def dashboard(request):
    stats = {
        "products": Product.objects.count(),
        "categories": Category.objects.count(),
        "orders": Order.objects.count(),
        "active_products": Product.objects.filter(is_active=True).count(),
    }
    return render(request, "backoffice/dashboard.html", {"stats": stats})

@staff_member_required
def product_list(request):
    qs = Product.objects.select_related("category").order_by("name")
    return render(request, "backoffice/product_list.html", {"products": qs})

@staff_member_required
def product_create(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Produit créé avec succès.")
            return redirect("fleur:bo_product_list")
    else:
        form = ProductForm()
    return render(request, "backoffice/product_form.html", {"form": form})

@staff_member_required
def category_list(request):
    qs = Category.objects.order_by("name")
    return render(request, "backoffice/category_list.html", {"categories": qs})

@staff_member_required
def category_create(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Catégorie créée avec succès.")
            return redirect("fleur:bo_category_list")
    else:
        form = CategoryForm()
    return render(request, "backoffice/category_form.html", {"form": form})

@staff_member_required
def order_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()

    orders = Order.objects.select_related("product", "slot").order_by("-id")

    if q:
        orders = orders.filter(
            Q(id__icontains=q) |
            Q(product__name__icontains=q) |
            Q(slot__code__icontains=q)
        )
    if status:
        orders = orders.filter(status=status)

    # distinct list of statuses for filter dropdown
    statuses = (
        Order.objects.order_by().values_list("status", flat=True).distinct()
    )

    return render(request, "backoffice/order_list.html", {
        "orders": orders,
        "q": q,
        "status": status,
        "statuses": statuses,
    })


@staff_member_required
def home_video_edit(request):
    content = HomeContent.get_solo()
    if request.method == "POST":
        form = HomeContentForm(request.POST, request.FILES, instance=content)
        if form.is_valid():
            form.save()
            messages.success(request, "Vidéo d’accueil mise à jour.")
            return redirect("fleur:bo_home_video")
    else:
        form = HomeContentForm(instance=content)
    return render(request, "backoffice/video_form.html", {"form": form})

@staff_member_required
def backoffice_slots_list(request):
    q = request.GET.get("q", "").strip()
    slots = Slot.objects.select_related("product").order_by("code")
    if q:
        slots = slots.filter(code__icontains=q) | slots.filter(product__name__icontains=q)

    return render(request, "backoffice/slots_list.html", {
        "slots": slots,
        "q": q,
    })

@staff_member_required
def backoffice_slot_create(request):
    if request.method == "POST":
        form = SlotForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Slot créé avec succès.")
            return redirect("fleur:bo_slots_list")
    else:
        form = SlotForm()
    return render(request, "backoffice/slot_form.html", {"form": form, "mode": "create"})

@staff_member_required
def backoffice_slot_edit(request, pk):
    slot = get_object_or_404(Slot, pk=pk)
    if request.method == "POST":
        form = SlotForm(request.POST, instance=slot)
        if form.is_valid():
            form.save()
            messages.success(request, "Slot mis à jour.")
            return redirect("fleur:bo_slots_list")
    else:
        form = SlotForm(instance=slot)
    return render(request, "backoffice/slot_form.html", {"form": form, "mode": "edit", "slot": slot})

@staff_member_required
def backoffice_slots_seed12(request):
    """Créer 12 slots code '1'..'12' s'ils n'existent pas."""
    created = 0
    for i in range(1, 13):
        _, was_created = Slot.objects.get_or_create(code=str(i))
        if was_created:
            created += 1
    messages.success(request, f"{created} slot(s) créé(s).")
    return redirect("fleur:bo_slots_list")