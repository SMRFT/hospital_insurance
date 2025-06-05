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
from .models import Register,Daycare
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
        


