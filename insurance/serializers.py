from rest_framework import serializers
from django.contrib.auth import authenticate
from bson import ObjectId
from django.core.validators import FileExtensionValidator
from datetime import date, datetime

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
    