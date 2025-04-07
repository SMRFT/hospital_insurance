from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse,HttpResponse, Http404
from django.contrib.auth.hashers import check_password
from pymongo import MongoClient
from gridfs import GridFS
from bson.objectid import ObjectId
import certifi
import os
from dotenv import load_dotenv

load_dotenv()
# Login view
from django.contrib.auth.hashers import make_password
from .models import Insurance ,Register
from .serializers import InsuranceSerializer ,RegisterSerializer
@api_view(['POST'])
@csrf_exempt
def registration(request):
    if request.method == 'POST':
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            # Hash the password
            serializer.validated_data['password'] = make_password(serializer.validated_data['password'])
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



# Login view
from django.contrib.auth.hashers import check_password

@api_view(['POST'])
@csrf_exempt
def login(request):
    email = request.data.get('email')
    password = request.data.get('password')
    try:
        user = Register.objects.get(email=email)
        if check_password(password, user.password):
            return JsonResponse({'message': 'Login successful!'}, status=status.HTTP_200_OK)
        else:
            return JsonResponse({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    except Register.DoesNotExist:
        return JsonResponse({'error': 'User does not exist'}, status=status.HTTP_404_NOT_FOUND)

    
    
# Insurance view

import logging
logger = logging.getLogger(__name__)

@api_view(['GET', 'POST'])
@csrf_exempt
def insurance(request):
    try:

        client = MongoClient(os.getenv("DB_HOST"))  # Connect to MongoDB
        db = client[os.getenv("DB_NAME")]           # Get the database
        fs = GridFS(db)                             # Initialize GridFS

        if request.method == 'POST':
            data = request.data.copy()
            billing_file = request.FILES.get('billingFile')
            query_file = request.FILES.get('queryUpload')
            query_response_file = request.FILES.get('queryResponse')
            
            # Log the files being received
            logger.debug(f"Received billing file: {billing_file}")
            logger.debug(f"Received query file: {query_file}")

            # Extract patient_uhid and patient_name for filename construction
            patient_uhid = data.get('patient_uhid', '').strip()
            patient_name = data.get('patient_name', '').strip()

            if not patient_uhid or not patient_name:
                return Response(
                    {"error": "patient_uhid and patient_name are required for file naming"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Save files to GridFS with customized filenames
            try:
                if billing_file:
                    billing_file_name = f"{patient_uhid}_{patient_name}_billing"
                    billing_file_id = fs.put(billing_file, filename=billing_file_name)
                    data['billingFile'] = str(billing_file_id)
                    del request.FILES['billingFile']  # 🛠 Remove file object

                if query_file:
                    query_file_name = f"{patient_uhid}_{patient_name}_query"
                    query_file_id = fs.put(query_file, filename=query_file_name)
                    data['queryUpload'] = str(query_file_id)
                    del request.FILES['queryUpload']  # 🛠 Remove file object

                if query_response_file:
                    query_response_file_name = f"{patient_uhid}_{patient_name}queryresponse"
                    query_response_file_id = fs.put(query_response_file, filename=query_response_file_name)
                    data['queryResponse'] = str(query_response_file_id)
                    del request.FILES['queryResponse']  # 🛠 Remove file object

                

                # Log the file ids
                logger.debug(f"Saved billing file id: {data['billingFile']}")
                logger.debug(f"Saved query file id: {data['queryUpload']}")
                logger.debug(f"Saved query response file id: {data['queryResponse']}")

            except Exception as gridfs_error:
                logger.error(f"GridFS Error: {gridfs_error}")
                return Response(
                    {"error": "File upload failed", "details": str(gridfs_error)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Validate and save the data
            serializer = InsuranceSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            logger.error(f"Serializer errors: {serializer.errors}")
            return Response({"error": "Invalid data", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        elif request.method == 'GET':
            insurances = Insurance.objects.all()
            serializer = InsuranceSerializer(insurances, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception("An error occurred during insurance processing")
        return Response({"error": "An error occurred", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def serve_file(request, file_id):
    # MongoDB connection


    client = MongoClient(os.getenv("DB_HOST"))  # Connect to MongoDB
    db = client[os.getenv("DB_NAME")]           # Get the database
    fs = GridFS(db)                             # Initialize GridFS                       # Initialize GridFS
    
    try:
        # Convert the file_id from string to ObjectId
        file_id = ObjectId(file_id)

        # Fetch the file from GridFS
        file = fs.get(file_id)

        # Serve the file as a response with PDF content type
        response = HttpResponse(file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename={file.filename}'
        return response

    except Exception as e:
        raise Http404(f"File not found: {str(e)}")
    
    

from pymongo import MongoClient
from gridfs import GridFS
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Daycare
from .serializers import DaycareSerializer
from datetime import datetime

@api_view(['POST', 'GET'])
def submit_daycare(request):
    # Connect to the MongoDB instance

    client = MongoClient(os.getenv("DB_HOST"))  # Connect to MongoDB
    db = client[os.getenv("DB_NAME")]           # Get the database
    fs = GridFS(db)                             # Initialize GridFS

    if request.method == 'POST':
        # Handle the file upload if a file is provided
        file = request.FILES.get('opFile')  # Expecting the file field to be named 'opFile'
        file_id = None

        if file:
            # Read the file as bytes
            file_data = file.read()  # This reads the file into a bytes object
            # Store the file in GridFS
            file_id = fs.put(file_data, filename=file.name, content_type=file.content_type)

        # Prepare the data for the serializer
        data = request.data.copy()
        if file_id:
            # Store the GridFS `_id` in the `opFile` field
            data['opFile'] = str(file_id)  # Convert ObjectId to string for JSON compatibility

        # Validate and save the Daycare object
        serializer = DaycareSerializer(data=data)
        if serializer.is_valid():
            serializer.save()  # Save data to the model, including the GridFS `_id`
            return Response({'message': 'Form submitted successfully!', '_id': str(file_id)}, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'GET':
        # Get all daycare records without filtering by date
        daycare_records = Daycare.objects.all()

        # Serialize the retrieved Daycare data
        serializer = DaycareSerializer(daycare_records, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)







@api_view(['PUT'])
@csrf_exempt
def insurance_update(request, bill_number):
    try:
        # Find the insurance record by bill number
        insurance = Insurance.objects.get(billNumber=bill_number)
        
        # Get data from request
        data = request.data.copy()
        
        # Handle file uploads
        client = MongoClient(os.getenv("DB_HOST"))
        db = client[os.getenv("DB_NAME")]
        fs = GridFS(db)
        
        billing_file = request.FILES.get('billingFile')
        query_file = request.FILES.get('queryUpload')
        query_response_file = request.FILES.get('queryResponse')
        
        # Extract patient info for filename construction
        patient_uhid = data.get('patient_uhid', insurance.patient_uhid).strip()
        patient_name = data.get('patient_name', insurance.patient_name).strip()
        
        # Handle the file uploads similar to the POST method
        if billing_file:
            billing_file_name = f"{patient_uhid}_{patient_name}_billing"
            billing_file_id = fs.put(billing_file, filename=billing_file_name)
            data['billingFile'] = str(billing_file_id)
        elif insurance.billingFile and 'billingFile' not in data:
            # Keep existing file if no new file is uploaded
            data['billingFile'] = insurance.billingFile
            
        if query_file:
            query_file_name = f"{patient_uhid}_{patient_name}_query"
            query_file_id = fs.put(query_file, filename=query_file_name)
            data['queryUpload'] = str(query_file_id)
        elif insurance.queryUpload and 'queryUpload' not in data:
            data['queryUpload'] = insurance.queryUpload
            
        if query_response_file:
            query_response_file_name = f"{patient_uhid}_{patient_name}_queryresponse"
            query_response_file_id = fs.put(query_response_file, filename=query_response_file_name)
            data['queryResponse'] = str(query_response_file_id)
        elif insurance.queryResponse and 'queryResponse' not in data:
            data['queryResponse'] = insurance.queryResponse
        
        # Update the record
        serializer = InsuranceSerializer(insurance, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response({"error": "Invalid data", "details": serializer.errors}, 
                        status=status.HTTP_400_BAD_REQUEST)
                        
    except Insurance.DoesNotExist:
        return Response({"error": "Insurance record not found"}, 
                        status=status.HTTP_404_NOT_FOUND)
                        
    except Exception as e:
        logger.exception("An error occurred during insurance update")
        return Response({"error": "An error occurred", "details": str(e)}, 
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)
