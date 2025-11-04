# fleur/api.py
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
import json
from .models import Payment, PaymentStatus, OrderStatus

API_KEY = "dev-secret"  # mets-la dans settings si tu veux

@csrf_exempt
def payment_insert_event(request):
    # Sécurité simple
    if request.headers.get("X-Api-Key") != API_KEY:
        return HttpResponseForbidden("bad key")

    data = json.loads(request.body.decode("utf-8"))
    payment_id = data.get("payment_id")
    amount = int(data.get("amount", 0))

    try:
        p = Payment.objects.select_related("order").get(pk=payment_id)
    except Payment.DoesNotExist:
        return JsonResponse({"ok": False, "error": "payment not found"}, status=404)

    # Idempotence: si déjà payé, on confirme seulement
    if p.status == PaymentStatus.SUCCEEDED:
        return JsonResponse({"ok": True, "completed": True})

    # Incrémente
    p.amount_inserted = (p.amount_inserted or 0) + amount
    if p.amount_inserted >= p.amount_due:
        p.status = PaymentStatus.SUCCEEDED
        p.order.status = OrderStatus.PAID
        p.order.save(update_fields=["status"])
        p.save(update_fields=["amount_inserted", "status"])
        return JsonResponse({"ok": True, "completed": True})

    p.save(update_fields=["amount_inserted"])
    return JsonResponse({"ok": True, "completed": False})
