import csv
import uuid
from datetime import date
from decimal import Decimal
from django.http import HttpResponse
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import (
    InvoiceSettings,
    ClientBillingSettings,
    ClientInvoice,
    InvoiceLine,
    ClientPayment,
    ClientPaymentDeduction,
    InvoiceAttendanceAnnexure
)
from .serializers import (
    InvoiceSettingsSerializer,
    ClientBillingSettingsSerializer,
    ClientInvoiceListSerializer,
    ClientInvoiceDetailSerializer,
    InvoiceLineSerializer,
    ClientPaymentSerializer,
    InvoiceAttendanceAnnexureSerializer,
    ManualLineCreateSerializer,
    PaymentRecordRequestSerializer,
    PaymentReversalSerializer,
    InvoiceCancelRequestSerializer,
    InvoiceQueryCreateSerializer
)
from .services import (
    BillingCalculationService,
    BillingRunService,
    InvoiceManagementService,
    PaymentReceivablesService,
    number_to_indian_words
)
from master_data.models import Client, ClientSite
from foundation.services.scope_service import check_permission, HasCapabilityAndScope
from foundation.services.audit_service import write_audit_event


class InvoiceSettingsView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'billing.configure'

    def get(self, request):
        if not check_permission(request.user, 'billing.configure'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        company_id = request.user.company_id
        settings = BillingCalculationService.get_company_settings(company_id)
        return Response(InvoiceSettingsSerializer(settings).data)

    def put(self, request):
        if not check_permission(request.user, 'billing.configure'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        company_id = request.user.company_id
        settings = BillingCalculationService.get_company_settings(company_id)
        serializer = InvoiceSettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ClientBillingSettingsListView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'billing.configure'

    def get(self, request):
        if not check_permission(request.user, 'billing.configure'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        company_id = request.user.company_id
        qs = ClientBillingSettings.objects.filter(company_id=company_id)
        client_id = request.query_params.get('client_id')
        if client_id:
            qs = qs.filter(client_id=client_id)
        return Response(ClientBillingSettingsSerializer(qs, many=True).data)

    def post(self, request):
        if not check_permission(request.user, 'billing.configure'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        company_id = request.user.company_id
        data = request.data.copy()
        data['company_id'] = company_id
        serializer = ClientBillingSettingsSerializer(data=data)
        if serializer.is_valid():
            serializer.save(company_id=company_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ClientBillingSettingsDetailView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'billing.configure'

    def get(self, request, pk):
        if not check_permission(request.user, 'billing.configure'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        setting = ClientBillingSettings.objects.filter(settings_id=pk, company_id=request.user.company_id).first()
        if not setting:
            return Response({'error': 'Settings not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ClientBillingSettingsSerializer(setting).data)

    def put(self, request, pk):
        if not check_permission(request.user, 'billing.configure'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        setting = ClientBillingSettings.objects.filter(settings_id=pk, company_id=request.user.company_id).first()
        if not setting:
            return Response({'error': 'Settings not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ClientBillingSettingsSerializer(setting, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BillingPreviewView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'billing.preview'

    def post(self, request):
        if not check_permission(request.user, 'billing.preview'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        company_id = request.user.company_id
        client_id = request.data.get('client_id')
        period_start = request.data.get('period_start')
        period_end = request.data.get('period_end')
        is_override = request.data.get('is_unlocked_period_override', False)
        override_reason = request.data.get('unlocked_period_reason')

        if not client_id or not period_start or not period_end:
            return Response({'error': 'client_id, period_start, and period_end are required.'}, status=status.HTTP_400_BAD_REQUEST)

        preview_data, skip_reason = BillingCalculationService.preview_client_billing(
            company_id=company_id,
            client_id=client_id,
            period_start=period_start,
            period_end=period_end,
            is_unlocked_period_override=is_override,
            unlocked_period_reason=override_reason
        )

        if skip_reason:
            return Response({'error': skip_reason}, status=status.HTTP_400_BAD_REQUEST)

        return Response(preview_data)


class BillingRunView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'billing.run'

    def post(self, request):
        if not check_permission(request.user, 'billing.run'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        company_id = request.user.company_id
        period_start = request.data.get('period_start')
        period_end = request.data.get('period_end')
        client_ids = request.data.get('client_ids')  # None = all clients
        is_override = request.data.get('is_unlocked_period_override', False)
        override_reason = request.data.get('unlocked_period_reason')

        if not period_start or not period_end:
            return Response({'error': 'period_start and period_end are required.'}, status=status.HTTP_400_BAD_REQUEST)

        res = BillingRunService.run_billing(
            company_id=company_id,
            period_start=period_start,
            period_end=period_end,
            client_ids=client_ids,
            user=request.user,
            is_unlocked_period_override=is_override,
            unlocked_period_reason=override_reason
        )
        return Response(res)


def _get_client_id_for_user(user):
    if getattr(user, 'client_company_id', None):
        return user.client_company_id
    if hasattr(user, 'email') and user.email:
        contact = ClientContact.objects.filter(email=user.email).first()
        if contact:
            return contact.client_id
    return None


class ClientInvoiceListView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'billing.view'

    def get(self, request):
        if not check_permission(request.user, 'billing.view'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        user = request.user
        qs = ClientInvoice.objects.filter(company_id=user.company_id)

        # Client role data isolation (PRD 2.4, 6.14, AC-11.59, AC-11.61)
        if user.role == 'CLIENT':
            client_id = _get_client_id_for_user(user)
            if not client_id:
                return Response({'error': 'No linked client organization.'}, status=status.HTTP_403_FORBIDDEN)
            # Clients see ONLY their own company's SENT or later invoices (DRAFTS ARE HIDDEN)
            qs = qs.filter(
                client_id=client_id,
                status__in=['SENT', 'PARTIALLY_PAID', 'PAID', 'CANCELLED']
            )
        else:
            # Admin filters
            client_filter = request.query_params.get('client_id')
            if client_filter:
                qs = qs.filter(client_id=client_filter)

        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        # Attach client name & code
        invoices_data = []
        clients_cache = {c.client_id: c for c in Client.objects.filter(company_id=user.company_id)}

        for inv in qs.order_by('-created_at'):
            d = ClientInvoiceListSerializer(inv).data
            c_obj = clients_cache.get(inv.client_id)
            if c_obj:
                d['client_name'] = c_obj.legal_name or c_obj.display_name
                d['client_code'] = c_obj.client_code
            invoices_data.append(d)

        return Response(invoices_data)


class ClientInvoiceDetailView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'billing.view'

    def get(self, request, pk):
        if not check_permission(request.user, 'billing.view'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        user = request.user
        invoice = ClientInvoice.objects.filter(invoice_id=pk, company_id=user.company_id).first()
        if not invoice:
            return Response({'error': 'Invoice not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Client data isolation check (AC-11.60, AC-11.61)
        if user.role == 'CLIENT':
            client_id = _get_client_id_for_user(user)
            if not client_id or invoice.client_id != client_id:
                return Response({'error': 'Access denied to this invoice (AC-11.60).'}, status=status.HTTP_403_FORBIDDEN)
            if not invoice.is_issued:
                return Response({'error': 'Draft invoices are not accessible to clients (AC-11.61).'}, status=status.HTTP_403_FORBIDDEN)

        # Populate related client & company metadata
        client_org = Client.objects.filter(client_id=invoice.client_id).first()
        serializer = ClientInvoiceDetailSerializer(invoice, context={'request': request})
        data = serializer.data

        if client_org:
            data['client_name'] = client_org.legal_name or client_org.display_name
            data['client_gstin'] = client_org.gstin
            data['client_pan'] = client_org.pan
            data['client_address'] = client_org.billing_address

        # Amount in words using Indian digit grouping (PRD 6.9, FR-11.116)
        data['total_in_words'] = number_to_indian_words(invoice.total_amount)

        # Attach line items
        lines = InvoiceLine.objects.filter(invoice_id=invoice.invoice_id).order_by('created_at')
        data['lines'] = InvoiceLineSerializer(lines, many=True).data

        # Attach payments
        payments = ClientPayment.objects.filter(invoice_id=invoice.invoice_id).order_by('-payment_date')
        data['payments'] = ClientPaymentSerializer(payments, many=True).data

        return Response(data)


class ManualLineCreateView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'billing.draft_edit'

    def post(self, request, pk):
        if not check_permission(request.user, 'billing.draft_edit'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = ManualLineCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            line = InvoiceManagementService.add_manual_line(pk, serializer.validated_data, request.user)
            return Response(InvoiceLineSerializer(line).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class InvoiceIssueView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'billing.issue'

    def post(self, request, pk):
        if not check_permission(request.user, 'billing.issue'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            issued = InvoiceManagementService.issue_invoice(pk, request.user)
            return Response({
                'message': 'Invoice successfully issued (AC-11.33).',
                'invoice_no': issued.invoice_no,
                'status': issued.status,
                'pdf_hash': issued.pdf_hash
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class InvoiceCancelView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'billing.cancel'

    def post(self, request, pk):
        if not check_permission(request.user, 'billing.cancel'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = InvoiceCancelRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            cancelled = InvoiceManagementService.cancel_invoice(
                invoice_id=pk,
                cancelled_reason=serializer.validated_data['cancelled_reason'],
                client_visible_reason=serializer.validated_data.get('client_visible_cancellation_reason'),
                user=request.user
            )
            return Response({
                'message': 'Invoice cancelled successfully (AC-11.39).',
                'invoice_no': cancelled.invoice_no,
                'status': cancelled.status
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class InvoiceReplacementCreateView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'billing.draft_edit'

    def post(self, request, pk):
        if not check_permission(request.user, 'billing.draft_edit'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            replacement = InvoiceManagementService.create_replacement_draft(pk, request.user)
            return Response({
                'message': 'Replacement draft created successfully (AC-11.40).',
                'replacement_draft_id': str(replacement.invoice_id),
                'draft_reference': replacement.draft_reference
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PaymentRecordView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'billing.record_payment'

    def post(self, request, pk):
        if not check_permission(request.user, 'billing.record_payment'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = PaymentRecordRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = PaymentReceivablesService.record_payment(pk, serializer.validated_data, request.user)
            return Response(ClientPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PaymentReversalView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'billing.reverse_payment'

    def post(self, request, pk):
        if not check_permission(request.user, 'billing.reverse_payment'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = PaymentReversalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = PaymentReceivablesService.reverse_payment(pk, serializer.validated_data['reversal_reason'], request.user)
            return Response(ClientPaymentSerializer(payment).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ReceivablesAgeingView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'billing.view'

    def get(self, request):
        if not check_permission(request.user, 'billing.view'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        data = PaymentReceivablesService.get_receivables_ageing(request.user.company_id)
        return Response(data)


class BillingDashboardMetricsView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'billing.view'

    def get(self, request):
        if not check_permission(request.user, 'billing.view'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        metrics = PaymentReceivablesService.get_dashboard_metrics(request.user.company_id)
        return Response(metrics)


class InvoiceAnnexureView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'billing.download_pdf'

    def get(self, request, pk):
        if not check_permission(request.user, 'billing.download_pdf'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        user = request.user
        invoice = ClientInvoice.objects.filter(invoice_id=pk, company_id=user.company_id).first()
        if not invoice:
            return Response({'error': 'Invoice not found.'}, status=status.HTTP_404_NOT_FOUND)

        if user.role == 'CLIENT':
            client_id = _get_client_id_for_user(user)
            if not client_id or invoice.client_id != client_id:
                return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

        annexures = InvoiceAttendanceAnnexure.objects.filter(invoice_id=invoice.invoice_id).order_by('duty_date')
        return Response(InvoiceAttendanceAnnexureSerializer(annexures, many=True).data)


class InvoiceQueryRaiseView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'billing.raise_query'

    def post(self, request, pk):
        if not check_permission(request.user, 'billing.raise_query'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = InvoiceQueryCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        invoice = ClientInvoice.objects.filter(invoice_id=pk, company_id=request.user.company_id).first()
        if not invoice:
            return Response({'error': 'Invoice not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Simulated or linked Module 8 ticket ID
        synthetic_ticket_id = uuid.uuid4()
        link = PaymentReceivablesService.link_invoice_query(
            invoice_id=invoice.invoice_id,
            ticket_id=synthetic_ticket_id,
            client_id=invoice.client_id,
            query_category=serializer.validated_data.get('query_category', 'INVOICE_QUERY')
        )
        return Response({
            'message': 'Query successfully registered. Payment reminders paused (AC-11.54, AC-11.55).',
            'ticket_id': str(synthetic_ticket_id),
            'under_query_flag': True
        })


class InvoiceExportCSVView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'billing.export'

    def get(self, request):
        if not check_permission(request.user, 'billing.export'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        company_id = request.user.company_id
        invoices = ClientInvoice.objects.filter(company_id=company_id).order_by('-invoice_date')

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="invoices_export_{date.today().isoformat()}.csv"'

        writer = csv.writer(response)
        # Documented, fixed column headers (PRD 6.14, AC-11.65)
        writer.writerow([
            'Invoice No',
            'Draft Ref',
            'Client ID',
            'Invoice Date',
            'Due Date',
            'Period Start',
            'Period End',
            'Subtotal',
            'Tax Amount',
            'Total Amount',
            'Paid Amount',
            'Deduction Amount',
            'Outstanding Amount',
            'Status',
            'Overdue',
            'Under Query'
        ])

        for inv in invoices:
            writer.writerow([
                inv.invoice_no or '',
                inv.draft_reference or '',
                str(inv.client_id),
                inv.invoice_date.isoformat() if inv.invoice_date else '',
                inv.due_date.isoformat() if inv.due_date else '',
                inv.period_start.isoformat(),
                inv.period_end.isoformat(),
                str(inv.subtotal),
                str(inv.tax_amount),
                str(inv.total_amount),
                str(inv.paid_amount),
                str(inv.deduction_amount),
                str(inv.outstanding_amount),
                inv.status,
                'YES' if inv.overdue_flag else 'NO',
                'YES' if inv.under_query_flag else 'NO'
            ])

        return response


class PaymentExportCSVView(APIView):
    permission_classes = [IsAuthenticated, HasCapabilityAndScope]
    required_capability = 'billing.export'

    def get(self, request):
        if not check_permission(request.user, 'billing.export'):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        company_id = request.user.company_id
        payments = ClientPayment.objects.filter(company_id=company_id).order_by('-payment_date')

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="payments_export_{date.today().isoformat()}.csv"'

        writer = csv.writer(response)
        # Documented, fixed column headers (PRD 6.14, AC-11.66)
        writer.writerow([
            'Payment ID',
            'Invoice ID',
            'Client ID',
            'Payment Date',
            'Amount',
            'Payment Method',
            'Reference No',
            'Status',
            'Unallocated Amount',
            'TDS Deductions',
            'Other Deductions'
        ])

        for p in payments:
            tds = sum(d.amount for d in ClientPaymentDeduction.objects.filter(payment_id=p.client_payment_id, deduction_type='TDS'))
            other = sum(d.amount for d in ClientPaymentDeduction.objects.filter(payment_id=p.client_payment_id, deduction_type='OTHER'))
            writer.writerow([
                str(p.client_payment_id),
                str(p.invoice_id),
                str(p.client_id),
                p.payment_date.isoformat(),
                str(p.amount),
                p.payment_method,
                p.reference_no or '',
                p.status,
                str(p.unallocated_amount),
                str(tds),
                str(other)
            ])

        return response
