# magda_app/views.py
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, redirect
from django.db.models import Q
from .models import Product, Category
from .forms import ProductForm

def landing(request):
    qs = Product.objects.filter(is_active=True)
    q = request.GET.get("q")
    cat = request.GET.get("cat")
    if q:
        qs = qs.filter(Q(name__icontains=q))
    if cat:
        qs = qs.filter(category__name=cat)
    categories = Category.objects.all()
    return render(request, "magda_app/landing.html",
                  {"products": qs, "categories": categories, "q": q, "cat": cat})

def product_detail(request, pk=None, slug=None):
    product = get_object_or_404(Product, pk=pk) if pk else get_object_or_404(Product, slug=slug)
    return render(request, "magda_app/product_detail.html", {"product": product})

def create_order(request, pk):
    if request.method != "POST":
        return redirect("magda:product_detail_pk", pk=pk)
    product = get_object_or_404(Product, pk=pk)
    Order.objects.create(product=product)
    messages.success(request, "Order received! We’ll contact you soon.")
    return redirect("magda:product_detail_pk", pk=pk)

@staff_member_required
def dashboard(request):
    total_products = Product.objects.count()
    total_categories = Category.objects.count()
    last_orders = Order.objects.select_related("product")[:8]
    top_products = Product.objects.annotate(n=Count("orders")).order_by("-n", "-id")[:5]
    return render(
        request,
        "magda_app/dashboard.html",
        {
            "total_products": total_products,
            "total_categories": total_categories,
            "last_orders": last_orders,
            "top_products": top_products,
        },
    )

@staff_member_required
def admin_product_list(request):
    qs = Product.objects.select_related("category")
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(category__name__icontains=q))
    paginator = Paginator(qs, 20)
    page = request.GET.get("page", 1)
    try:
        products = paginator.page(page)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)
    return render(request, "magda_app/admin_product_list.html", {"products": products, "q": q})

@staff_member_required
def product_create(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Product created.")
            return redirect("magda:admin_product_list")
    else:
        form = ProductForm()
    return render(request, "magda_app/admin_product_form.html", {"form": form})
