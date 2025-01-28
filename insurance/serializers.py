from rest_framework import serializers
from django.contrib.auth import authenticate

#Register Serializer
from .models import Register,Daycare
class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Register
        fields = '__all__'

    def validate(self, data):
        if data['password'] != data['confirmPassword']:
            raise serializers.ValidationError("Passwords do not match.")
        return data
    
#Login Serializer 
from .models import Login
class LoginSerializer(serializers.ModelSerializer):
    class Meta:
        model =   Login
        fields = '__all__'

class DaycareSerializer(serializers.ModelSerializer):
    class Meta:
        model = Daycare
        fields = '__all__'  # Include all fields from the model
        
from rest_framework import serializers
from .models import Insurance

class InsuranceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Insurance
        fields = '__all__'

    def validate(self, data):
        if not data.get('billNumber'):
            raise serializers.ValidationError("billNumber is required.")
        return data

