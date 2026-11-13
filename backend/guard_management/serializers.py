from rest_framework import serializers
from guard_management.models import (
    Employee, EmployeeDocument, EmployeeTraining, EmployeeCheck,
    LeaveRequest, GuardStatusHistory, GuardDisciplinaryRecord,
    GuardIdCard, ProfileChangeRequest
)
from guard_management import services


class EmployeeDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeDocument
        fields = '__all__'


class EmployeeTrainingSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeTraining
        fields = '__all__'


class EmployeeCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeCheck
        fields = '__all__'


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)
    guard_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = LeaveRequest
        fields = '__all__'


class GuardStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = GuardStatusHistory
        fields = '__all__'


class GuardDisciplinaryRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuardDisciplinaryRecord
        fields = '__all__'


class GuardIdCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuardIdCard
        fields = '__all__'


class ProfileChangeRequestSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)

    class Meta:
        model = ProfileChangeRequest
        fields = '__all__'


class EmployeeListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    deployability = serializers.SerializerMethodField()
    post_type_name = serializers.CharField(source='post_type.name', read_only=True)

    class Meta:
        model = Employee
        fields = [
            'employee_id', 'employee_code', 'full_name', 'phone', 'gender',
            'lifecycle_status', 'date_joined', 'post_type_name', 'home_district',
            'reference_photo_url', 'is_ex_serviceman', 'deployability'
        ]

    def get_deployability(self, obj):
        return services.is_guard_deployable_on_date(obj.employee_id)


class EmployeeDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    documents = serializers.SerializerMethodField()
    trainings = EmployeeTrainingSerializer(many=True, read_only=True)
    checks = EmployeeCheckSerializer(many=True, read_only=True)
    leaves = LeaveRequestSerializer(many=True, read_only=True)
    status_history = GuardStatusHistorySerializer(many=True, read_only=True)
    disciplinary_records = serializers.SerializerMethodField()
    masked_bank_details = serializers.SerializerMethodField()
    deployability = serializers.SerializerMethodField()
    post_type_name = serializers.CharField(source='post_type.name', read_only=True)

    class Meta:
        model = Employee
        fields = '__all__'

    def get_documents(self, obj):
        docs = obj.documents.filter(is_active=True).order_by('-version')
        return EmployeeDocumentSerializer(docs, many=True).data

    def get_disciplinary_records(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.role == 'GUARD':
            records = obj.disciplinary_records.filter(is_visible_to_guard=True)
        else:
            records = obj.disciplinary_records.all()
        return GuardDisciplinaryRecordSerializer(records, many=True).data

    def get_masked_bank_details(self, obj):
        raw = obj.bank_details or {}
        acct = str(raw.get('account_number', ''))
        return {
            'bank_name': raw.get('bank_name', 'N/A'),
            'account_holder_name': raw.get('account_holder_name', 'N/A'),
            'account_number_masked': f"XXXX-XXXX-{acct[-4:]}" if len(acct) >= 4 else (acct or 'Not configured'),
            'ifsc': raw.get('ifsc', 'N/A')
        }

    def get_deployability(self, obj):
        return services.is_guard_deployable_on_date(obj.employee_id)

