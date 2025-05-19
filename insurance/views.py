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
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import permission_classes
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from bson import ObjectId

from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.tokens import RefreshToken
from pymongo import MongoClient
from datetime import datetime
from insurance.auth.permissions import SkipPermissionsIfDisabled
from pyauth.auth import HasRoleAndDataPermission
#permisiins disabled 

from dotenv import load_dotenv
load_dotenv()
# Register view
from .models import Insurance ,Register, Daycare
from .serializers import InsuranceSerializer ,RegisterSerializer, DaycareSerializer



mongo_uri = os.getenv("GLOBAL_DB_HOST")



@api_view(['POST'])
@csrf_exempt
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def registration(request):
    if request.method == 'POST':
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()  # Only save, don't re-hash
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Login view
@api_view(['POST'])
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def login(request):
    employee_id = request.data.get('id')
    password = request.data.get('password')

    try:
        user = Register.objects.get(id=employee_id)
        if check_password(password, user.password):
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'role': user.role,
                    'name': user.name if hasattr(user, 'name') else 'Admin',
                },
                'token': str(refresh.access_token),
                'message': 'Login successful'
            }, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'Invalid ID or password'}, status=status.HTTP_401_UNAUTHORIZED)
    except Register.DoesNotExist:
        return Response({'message': 'User does not exist'}, status=status.HTTP_404_NOT_FOUND)

  
# Insurance view
import logging
logger = logging.getLogger(__name__)

@api_view(['GET', 'POST'])
@csrf_exempt
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def insurance(request):
    try:

        
        client = MongoClient(mongo_uri)
        db = client["Insurance"]         
        fs = GridFS(db)                  

        if request.method == 'POST':
            data = request.data.copy()
            billing_file = request.FILES.get('billingFile')
            query_file = request.FILES.get('queryUpload')
            query_response_file = request.FILES.get('queryResponse')

            # Extract patient_uhid and patient_name for file naming
            patient_uhid = data.get('patient_uhid', '').strip()
            patient_name = data.get('patient_name', '').strip()

            # Only validate patient_uhid and patient_name if any file is being uploaded
            if any([billing_file, query_file, query_response_file]) and (not patient_uhid or not patient_name):
                return Response(
                    {"error": "patient_uhid and patient_name are required for file naming if uploading files"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                # Save files to GridFS if present
                if billing_file:
                    billing_file_name = f"{patient_uhid}_{patient_name}_billing"
                    billing_file_id = fs.put(billing_file, filename=billing_file_name)
                    data['billingFile'] = str(billing_file_id)

                if query_file:
                    query_file_name = f"{patient_uhid}_{patient_name}_query"
                    query_file_id = fs.put(query_file, filename=query_file_name)
                    data['queryUpload'] = str(query_file_id)

                if query_response_file:
                    query_response_file_name = f"{patient_uhid}_{patient_name}_queryresponse"
                    query_response_file_id = fs.put(query_response_file, filename=query_response_file_name)
                    data['queryResponse'] = str(query_response_file_id)

            except Exception as gridfs_error:
                logger.error(f"GridFS Error: {gridfs_error}")
                return Response(
                    {"error": "File upload failed", "details": str(gridfs_error)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Validate and save the rest of the form data
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


@api_view(['POST', 'GET'])
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def serve_file(request, file_id):
    # MongoDB connection
    
    client = MongoClient(mongo_uri)
    db = client["Insurance"]         
    fs = GridFS(db)                  
    
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
    
    
@api_view(['POST', 'GET'])
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def submit_daycare(request):
    # Connect to the MongoDB instance

    client = MongoClient(mongo_uri)
    db = client["Insurance"]         
    fs = GridFS(db)     

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


logger = logging.getLogger(__name__)
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
@api_view(['PUT','GET','POST'])
@csrf_exempt
def insurance_update_combined(request, identifier):
    try:
        logger.info(f"Attempting to update record with identifier: {identifier}")
        incoming_data = request.data.copy()

        # Parse date
        update_date = incoming_data.get("date")
        if not update_date:
            return Response({"error": "Date is required for update."}, status=400)
        
        try:
            parsed_date = datetime.strptime(update_date, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        # Find record
        insurance = None
        if identifier.upper().startswith("OP"):
            insurance = Insurance.objects.filter(opNumber=identifier, date=parsed_date).first()
        elif identifier.upper().startswith("IP"):
            insurance = Insurance.objects.filter(ipNumber=identifier, date=parsed_date).first()
        else:
            insurance = (
                Insurance.objects.filter(billNumber=identifier, date=parsed_date).first()
                or Insurance.objects.filter(opNumber__endswith=identifier, date=parsed_date).first()
                or Insurance.objects.filter(ipNumber__endswith=identifier, date=parsed_date).first()
            )

        if not insurance:
            return Response({"error": f"No record found for identifier {identifier} and date {update_date}"}, status=404)

        # Connect to GridFS
        client = MongoClient(mongo_uri)
        db = client["Insurance"]
        fs = GridFS(db)

        # Preserve existing fields unless new ones are provided
        updated_fields = {}

        for field in ["patient_uhid", "patient_name", "paymentType"]:
            value = incoming_data.get(field)
            if value is not None:
                updated_fields[field] = value.strip()

        # Handle file uploads
        patient_uhid = updated_fields.get("patient_uhid", insurance.patient_uhid)
        patient_name = updated_fields.get("patient_name", insurance.patient_name)

        for file_field, suffix in [
            ("billingFile", "billing"),
            ("queryUpload", "query"),
            ("queryResponse", "queryresponse"),
        ]:
            upload = request.FILES.get(file_field)
            if upload:
                file_name = f"{patient_uhid}_{patient_name}_{suffix}"
                file_id = fs.put(upload, filename=file_name)
                updated_fields[file_field] = str(file_id)
            else:
                # Retain old file reference if not updated
                existing_value = getattr(insurance, file_field)
                if existing_value:
                    updated_fields[file_field] = existing_value

        # Handle numeric fields
        for field in ["billAmount", "claimedAmount", "settledAmount", "approvalAmount", "pendingAmount"]:
            raw_val = incoming_data.get(field)
            if raw_val in ["", None]:
                continue  # skip updating if not provided
            try:
                updated_fields[field] = float(raw_val)
            except (ValueError, TypeError):
                return Response({"error": f"Invalid numeric value for {field}"}, status=400)

        # Handle edit history
        edit_history_json = incoming_data.get("editHistory")
        if edit_history_json:
            try:
                if isinstance(edit_history_json, str):
                    clean_json = edit_history_json.strip('"').replace('\\"', '"')
                    edit_history = json.loads(clean_json)
                else:
                    edit_history = edit_history_json
                updated_fields["editHistory"] = edit_history
            except Exception as e:
                return Response({"error": "Failed to parse edit history"}, status=400)

        # Ensure _id is not present
        updated_fields.pop("_id", None)

        # Serialize and update
        serializer = InsuranceSerializer(insurance, data=updated_fields, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Insurance updated successfully", "data": serializer.data}, status=200)
        else:
            return Response({"error": "Invalid data", "details": serializer.errors}, status=400)

    except Exception as e:
        logger.exception("Unexpected error during update")
        return Response({"error": "An error occurred", "details": str(e)}, status=500)
    

@api_view(['GET'])
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def get_insurance_companies(request):
    try:
        # MongoDB connection
        client = MongoClient(mongo_uri)
        db = client["Insurance"]
        collection = db["insurance_company"]

        # Fetch all documents
        insurance_companies = list(collection.find({}, {"_id": 0}))  # Exclude _id from response

        return JsonResponse(insurance_companies, safe=False, status=200)

    except Exception as e:
        return JsonResponse({"error": "Failed to fetch insurance companies", "details": str(e)}, status=500)
