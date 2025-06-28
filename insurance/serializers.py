from rest_framework import serializers
from django.contrib.auth import authenticate
from bson import ObjectId
from django.core.validators import FileExtensionValidator

class ObjectIdField(serializers.Field):
    def to_representation(self, value):
        return str(value)
    def to_internal_value(self, data):
        return ObjectId(data)

#Register Serializer
from .models import Register,Daycare,OtherRecord
class RegisterSerializer(serializers.ModelSerializer):
    confirmPassword = serializers.CharField(write_only=True)

    class Meta:
        model = Register
        fields = ['email', 'password', 'confirmPassword', 'name','id','role']  # list your actual fields
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate(self, data):
        if data['password'] != data['confirmPassword']:
            raise serializers.ValidationError("Passwords do not match.")
        return data

    def create(self, validated_data):
        validated_data.pop('confirmPassword')  # Remove it before creating the object
        return super().create(validated_data)

    
#Login Serializer 
from .models import Login
class LoginSerializer(serializers.ModelSerializer):
    id = ObjectIdField(read_only=True)
    class Meta:
        model =   Login
        fields = '__all__'

class DaycareSerializer(serializers.ModelSerializer):
    id = ObjectIdField(read_only=True)
    class Meta:
        model = Daycare
        fields = '__all__'  # Include all fields from the model
        

from .models import Insurance
class InsuranceSerializer(serializers.ModelSerializer):
    id = ObjectIdField(read_only=True)
    class Meta:
        model = Insurance
        fields = '__all__'


from rest_framework import serializers
from bson import ObjectId
from datetime import date, datetime

class ObjectIdField(serializers.Field):
    """Custom field to handle MongoDB ObjectId"""
    
    def to_representation(self, value):
        if isinstance(value, ObjectId):
            return {'$oid': str(value)}
        return value
    
    def to_internal_value(self, data):
        if isinstance(data, dict) and '$oid' in data:
            return ObjectId(data['$oid'])
        elif isinstance(data, str):
            return ObjectId(data)
        return data

class OtherRecordSerializer(serializers.Serializer):
    id = ObjectIdField(read_only=True)
    date = serializers.CharField(required=False, allow_blank=True, allow_null=True)  # Changed to CharField to handle string dates
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
    

    


