import random

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from kvn_notify import notify


class SendDemo(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        amount = f"{random.randint(5, 80)} EUR"
        notify(request.user, "demo.expense_added", {"who": "Ana", "amount": amount, "group": "Trip to Berat"})
        return Response({"sent": True}, status=202)
