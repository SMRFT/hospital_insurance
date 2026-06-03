from rest_framework import serializers
from django.contrib.auth import authenticate
from bson import ObjectId
from django.core.validators import FileExtensionValidator
from datetime import date, datetime
from pymongo import MongoClient
import os

def get_employee_name_by_id(employee_id):
    """Get employee name from Global database by employee ID"""
    try:
        mongo_url = os.getenv("GLOBAL_DB_HOST")
        client = MongoClient(mongo_url)
        db = client["Global"]
        collection = db["backend_diagnostics_profile"]
        
        employee = collection.find_one({"employeeId": str(employee_id)})
        
        if employee:
            return employee.get('employeeName', str(employee_id))
        return str(employee_id)
    except Exception as e:
        print(f"Error fetching employee name: {str(e)}")
        return str(employee_id)
    finally:
        if 'client' in locals():
            client.close()

class ObjectIdField(serializers.Field):
    def to_representation(self, value):
        return str(value)
    def to_internal_value(self, data):
        return ObjectId(data)


#Daycare Serializer 
from .models import Daycare
class DaycareSerializer(serializers.ModelSerializer):
    id = ObjectIdField(read_only=True)
    class Meta:
        model = Daycare
        fields = '__all__' 


#Insurance Serializer
from .models import Insurance

class InsuranceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Insurance
        fields = "__all__"

    def validate_billingFile(self, value):
        if isinstance(value, str):  # GridFS ID already stored
            return value
        return value


from .models import Enquiry, FollowUp
class FollowUpSerializer(serializers.ModelSerializer):
    enquiry_id = serializers.IntegerField(
        source='enquiry.enquiry_id',
        read_only=True
    )

    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = FollowUp
        fields = [
            "followup_id",
            "enquiry",
            "enquiry_id",
            "followup_date",
            "followup_Remarks",
            "created_by",
            "created_by_name",
            "created_date",
            "lastmodified_by",
            "lastmodified_date"
        ]
        read_only_fields = ["followup_id", "enquiry_id"]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return get_employee_name_by_id(obj.created_by)
        return None
    
    def to_representation(self, instance):
        """Return enquiry_id in the response."""
        ret = super().to_representation(instance)
        ret['enquiry_id'] = instance.enquiry.enquiry_id
        return ret


class EnquirySerializer(serializers.ModelSerializer):
    follow_ups = FollowUpSerializer(many=True, read_only=True)

    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Enquiry
        fields = [
            "enquiry_id",
            "date",
            "ipNumber",
            "opNumber",
            "patientName",
            "phoneNumber",
            "insuranceName",
            "specificInsuranceCompany",
            "reasonForApproach",
            "created_by",
            "created_by_name",
            "created_date",
            "lastmodified_by",
            "lastmodified_date",
            "follow_ups",
        ]
        read_only_fields = ["enquiry_id"]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return get_employee_name_by_id(obj.created_by)
        return None
      


class OtherRecordSerializer(serializers.Serializer):
    id = ObjectIdField(read_only=True)
    date = serializers.CharField(required=False, allow_blank=True, allow_null=True)  
    patient_name = serializers.CharField(max_length=200)
    patient_uhid = serializers.CharField(max_length=50)
    mobile_number = serializers.CharField(max_length=15)
    company_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    treatment = serializers.CharField(max_length=500, required=False, allow_blank=True)
    refund = serializers.CharField(max_length=500, required=False, allow_blank=True)
    payment_details = serializers.ListField(default=list)
    total_amount = serializers.SerializerMethodField()
    
    def get_total_amount(self, obj):
        """Calculate total amount from payment details"""
        payment_details = obj.get('payment_details', [])
        if not payment_details:
            return 0
        return sum(float(payment.get('amount', 0)) for payment in payment_details)
    
    def validate_date(self, value):
        """Validate and convert date field"""
        if not value:
            return None
        
        # If it's already a string, return as is
        if isinstance(value, str):
            return value
        
        # If it's a date object, convert to string
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        
        return value