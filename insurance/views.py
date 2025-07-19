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
import mimetypes
# import magic
import os
from rest_framework.decorators import permission_classes
import json
import logging
from django.http import JsonResponse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods
from bson import ObjectId
from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.tokens import RefreshToken
from pymongo import MongoClient
from datetime import datetime
from pyauth.auth import HasRolePermission 
from dotenv import load_dotenv
import logging
from datetime import datetime
from django.db.models import Q
logger = logging.getLogger(__name__)
load_dotenv()

from .models import Insurance , Daycare, OtherRecord
from .serializers import InsuranceSerializer , DaycareSerializer , OtherRecordSerializer

mongo_uri = os.getenv("GLOBAL_DB_HOST")

# Insurance view
@api_view(['GET', 'POST'])
@csrf_exempt
@permission_classes([ HasRolePermission])
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

            # Check if patient_uhid already exists for today's date
            if patient_uhid:
                submission_date = data.get('date')
                if not submission_date:
                    submission_date = datetime.now().date()
                else:
                    try:
                        submission_date = datetime.strptime(submission_date, '%Y-%m-%d').date()
                    except ValueError:
                        submission_date = datetime.now().date()
                
                # Check for existing records with same patient_uhid and date
                existing_records = Insurance.objects.filter(
                    patient_uhid=patient_uhid,
                    date=submission_date
                )
                
                if existing_records.exists():
                    return Response(
                        {"error": f"This patient UHID ({patient_uhid}) for date {submission_date} is already stored in the database."},
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

            # Store patient_uhid in opNumber if it's an OP case
            op_number = data.get('opNumber')
            if op_number and not data.get('ipNumber'):
                # For OP cases, store patient_uhid in opNumber
                data['opNumber'] = patient_uhid

            # Validate and save the rest of the form data
            serializer = InsuranceSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)

            logger.error(f"Serializer errors: {serializer.errors}")
            return Response({"error": "Invalid data", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        elif request.method == 'GET':
            # Start with all insurance records
            insurances = Insurance.objects.all()
            
            # Apply company filter
            company_name = request.GET.get('companyName')
            if company_name:
                insurances = insurances.filter(companyName=company_name)
            
            # Apply date range filter
            from_date = request.GET.get('from_date')
            to_date = request.GET.get('to_date')
            
            if from_date:
                try:
                    from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
                    insurances = insurances.filter(date__gte=from_date_obj)
                except ValueError:
                    logger.warning(f"Invalid from_date format: {from_date}")
            
            if to_date:
                try:
                    to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date()
                    insurances = insurances.filter(date__lte=to_date_obj)
                except ValueError:
                    logger.warning(f"Invalid to_date format: {to_date}")
            
            # Apply search filter
            search_field = request.GET.get('search_field')
            search_value = request.GET.get('search_value')
            
            if search_field and search_value:
                search_filter = Q()
                
                if search_field == 'billNumber':
                    search_filter = Q(billNumber__icontains=search_value)
                elif search_field == 'ipNumber':
                    search_filter = Q(ipNumber__icontains=search_value)
                elif search_field == 'opNumber':
                    search_filter = Q(opNumber__icontains=search_value)
                elif search_field == 'patient_name':
                    search_filter = Q(patient_name__icontains=search_value)
                elif search_field == 'dateOfDischarge':
                    try:
                        discharge_date_obj = datetime.strptime(search_value, '%Y-%m-%d').date()
                        search_filter = Q(dateOfDischarge=discharge_date_obj)
                    except ValueError:
                        logger.warning(f"Invalid dateOfDischarge format: {search_value}")
                        # If date format is invalid, return empty queryset
                        insurances = Insurance.objects.none()
                
                if search_filter:
                    insurances = insurances.filter(search_filter)
            
            # Order by date descending (most recent first)
            insurances = insurances.order_by('-date', '-id')
            
            serializer = InsuranceSerializer(insurances, many=True)
            
            logger.info(f"Filtered insurance records: {len(serializer.data)} results")
            return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception("An error occurred during insurance processing")
        return Response({"error": "An error occurred", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@csrf_exempt
@permission_classes([ HasRolePermission])
def check_patient_exists(request):
    ipNumber = request.GET.get("ipNumber")
    date_str = request.GET.get("date")

    if not ipNumber or not date_str:
        return Response(
            {"error": "Missing required parameters: ipNumber and date"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return Response({"error": "Invalid date format"}, status=status.HTTP_400_BAD_REQUEST)

    exists = Insurance.objects.filter(ipNumber=ipNumber, date=date_obj).exists()
    return Response({"exists": exists})


# @api_view(['GET'])
# @permission_classes([ HasRolePermission])
# def serve_file(request, file_id):
#     client = MongoClient(mongo_uri)
#     db = client["Insurance"]
#     fs = GridFS(db)

#     try:
#         file_id = ObjectId(file_id)
#         file = fs.get(file_id)

#         # Step 1: Try to get MIME type from filename
#         content_type, _ = mimetypes.guess_type(file.filename)

#         # Step 2: Fallback using magic (binary detection)
#         if not content_type:
#             mime = magic.Magic(mime=True)
#             content_type = mime.from_buffer(file.read(2048))
#             file.seek(0)

#         response = HttpResponse(file.read(), content_type=content_type)

#         # View inline (NOT as download)
#         response['Content-Disposition'] = f'inline; filename="{file.filename}"'

#         return response

#     except Exception as e:
#         raise Http404(f"File not found: {str(e)}")
    
    
@api_view(['POST', 'GET'])
@permission_classes([ HasRolePermission])
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



@api_view(['PUT'])
@csrf_exempt
@permission_classes([ HasRolePermission])
def insurance_update_combined(request, identifier):
    try:
        logger.info(f"Attempting to update record with identifier: {identifier}")
        data = request.data.copy()

        # Normalize date
        update_date = data.get("date")
        if update_date:
            try:
                parsed_date = datetime.strptime(update_date, "%Y-%m-%d").date()
            except ValueError:
                return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)
        else:
            return Response({"error": "Date is required for update."}, status=400)

        # Identify the insurance object
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
            raise Insurance.DoesNotExist(f"No record found for identifier {identifier} and date {update_date}")

        # Connect to MongoDB GridFS
        client = MongoClient(mongo_uri)
        db = client["Insurance"]
        fs = GridFS(db)

        # File handling
        patient_uhid = data.get("patient_uhid", insurance.patient_uhid).strip()
        patient_name = data.get("patient_name", insurance.patient_name).strip()

        for file_field, suffix in [
            ("billingFile", "billing"),
            ("queryUpload", "query"),
            ("queryResponse", "queryresponse"),
        ]:
            upload = request.FILES.get(file_field)
            if upload:
                file_name = f"{patient_uhid}_{patient_name}_{suffix}"
                file_id = fs.put(upload, filename=file_name)
                data[file_field] = str(file_id)
            elif getattr(insurance, file_field):
                data[file_field] = getattr(insurance, file_field)

        # Numeric fields cleanup
        for field in ["billAmount", "claimedAmount", "settledAmount", "approvalAmount", "pendingAmount"]:
            val = data.get(field)
            if val in ["", None]:
                data[field] = None
            else:
                try:
                    data[field] = float(val)
                except (ValueError, TypeError):
                    data[field] = None

                    # Edit history parsing
                    edit_history_json = data.get("editHistory")
                    edit_history = []
                    if edit_history_json:
                        try:
                            if isinstance(edit_history_json, str):
                                # Attempt to parse with safety
                                clean_json = edit_history_json
                                if clean_json.startswith('"') and clean_json.endswith('"'):
                                    clean_json = clean_json[1:-1]
                                clean_json = clean_json.replace('\\"', '"')
                                edit_history = json.loads(clean_json)
                            elif isinstance(edit_history_json, list):
                                edit_history = edit_history_json
                        except Exception as e:
                            logger.error(f"Failed to parse editHistory: {e}")
                            return Response({"error": "Failed to parse edit history"}, status=400)

                    # Update model fields
                    for field in [
                        "billAmount", "claimedAmount", "settledAmount", "approvalAmount", "pendingAmount",
                        "paymentType", "billingFile", "queryUpload", "queryResponse"
                    ]:
                        if field in data:
                            setattr(insurance, field, data[field])

                    # Update the edit history
                    if edit_history:
                        insurance.editHistory = edit_history

                    insurance.save()
                    return JsonResponse({"message": "Record updated successfully"}, status=200)

                except Insurance.DoesNotExist as e:
                    return JsonResponse({"error": str(e)}, status=404)
                except Exception as e:
                    logger.exception("Unexpected error during update")
                    return JsonResponse({"error": str(e)}, status=500)

        
        # Ensure _id is not in the data to avoid conflicts
        if '_id' in data:
            del data['_id']
        
        # Use the serializer for the update
        serializer = InsuranceSerializer(insurance, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Insurance updated successfully", 
                "data": serializer.data
            }, status=200)
        else:
            return Response({
                "error": "Invalid data", 
                "details": serializer.errors
            }, status=400)
            
    except Insurance.DoesNotExist as e:
        logger.error(f"Record not found for identifier: {identifier}")
        return Response({
            "error": f"Insurance record not found with identifier: {identifier}",
            "details": str(e)
        }, status=404)
    except Exception as e:
        logger.exception(f"Error occurred during insurance update: {str(e)}")
        return Response({
            "error": "An error occurred", 
            "details": str(e)
        }, status=500)
    

@api_view(['GET'])
@permission_classes([ HasRolePermission])
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


from datetime import datetime, date
def convert_dates_to_strings(data):
    """Convert datetime.date objects to strings for MongoDB compatibility"""
    if isinstance(data, dict):
        return {key: convert_dates_to_strings(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_dates_to_strings(item) for item in data]
    elif isinstance(data, date):
        return data.isoformat()  # Convert date to YYYY-MM-DD string
    elif isinstance(data, datetime):
        return data.isoformat()  # Convert datetime to ISO string
    else:
        return data

@api_view(['GET'])
@permission_classes([ HasRolePermission])
def other_record_report_view(request):
    """
    Get flattened report data where each payment entry becomes a separate row
    Filters by individual payment dates only
    """
    try:
        client = MongoClient(mongo_uri)
        db = client["Insurance"]
        collection = db["insurance_otherrecord"]
        
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        
        # Get all records
        records = list(collection.find({}))
        flattened_data = []
        
        for record in records:
            # Only process records that have payment_details
            if record.get('payment_details'):
                for payment in record['payment_details']:
                    payment_date = payment.get('date', '')
                    
                    # Skip if no payment date
                    if not payment_date:
                        continue
                    
                    # Apply date filtering
                    if from_date and payment_date < from_date:
                        continue
                    if to_date and payment_date > to_date:
                        continue
                    
                    # Add to results - each payment becomes one row
                    flattened_data.append({
                        'id': str(record['_id']),
                        'date': payment_date,
                        'patient_name': record.get('patient_name', ''),
                        'patient_uhid': record.get('patient_uhid', ''),
                        'mobile_number': record.get('mobile_number', ''),
                        'company_name': record.get('company_name', ''),
                        'treatment': record.get('treatment', ''),
                        'amount': payment.get('amount', 0),
                        'payment_method': payment.get('payment_method', ''),
                        'refund': record.get('refund', 0)
                    })
        
        # Sort by date
        flattened_data.sort(key=lambda x: x['date'])
        
        return Response(flattened_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        if 'client' in locals():
            client.close()


@api_view(['GET', 'POST', 'PUT'])
@permission_classes([ HasRolePermission])
def other_record_view(request):
    try:
        client = MongoClient(mongo_uri)
        db = client["Insurance"]
        collection = db["insurance_otherrecord"]
        
        if request.method == 'GET':
            from_date = request.GET.get('from_date')
            to_date = request.GET.get('to_date')
            
            # Get all records
            records = list(collection.find({}))
            processed_records = []
            
            for record in records:
                # Only process records that have payment_details
                if record.get('payment_details'):
                    # Filter payment details by date
                    filtered_payments = []
                    for payment in record['payment_details']:
                        payment_date = payment.get('date', '')
                        
                        # Skip if no payment date
                        if not payment_date:
                            continue
                        
                        # Apply date filtering
                        if from_date and payment_date < from_date:
                            continue
                        if to_date and payment_date > to_date:
                            continue
                        
                        filtered_payments.append(payment)
                    
                    # Only include record if it has matching payments
                    if filtered_payments:
                        record_copy = record.copy()
                        record_copy['payment_details'] = filtered_payments
                        processed_records.append(record_copy)
            
            # Convert ObjectId to proper format for serialization
            for record in processed_records:
                record['id'] = record['_id']
                del record['_id']
            
            serializer = OtherRecordSerializer(processed_records, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        elif request.method == 'POST':
            serializer = OtherRecordSerializer(data=request.data)
            if serializer.is_valid():
                validated_data = serializer.validated_data
                validated_data['created_at'] = datetime.now()
                validated_data['updated_at'] = datetime.now()
                validated_data = convert_dates_to_strings(validated_data)
                
                result = collection.insert_one(validated_data)
                created_record = collection.find_one({'_id': result.inserted_id})
                created_record['id'] = created_record['_id']
                del created_record['_id']
                
                response_serializer = OtherRecordSerializer(created_record)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        elif request.method == 'PUT':
            record_id = request.data.get('id')
            if not record_id:
                return Response({'error': 'ID is required for update'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                if isinstance(record_id, dict) and '$oid' in record_id:
                    object_id = ObjectId(record_id['$oid'])
                elif isinstance(record_id, str):
                    object_id = ObjectId(record_id)
                else:
                    object_id = ObjectId(record_id)
            except Exception as e:
                return Response({'error': f'Invalid ID format: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

            record = collection.find_one({"_id": object_id})
            if not record:
                return Response({'error': 'Record not found'}, status=status.HTTP_404_NOT_FOUND)

            update_data = {}
            basic_fields = ['date', 'patient_name', 'patient_uhid', 'mobile_number', 
                          'company_name', 'treatment', 'refund']
            
            for field in basic_fields:
                if field in request.data:
                    update_data[field] = request.data[field]

            new_payments = request.data.get("payment_details", [])
            if new_payments:
                serializer = OtherRecordSerializer(data={'payment_details': new_payments}, partial=True)
                if not serializer.is_valid():
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
                existing_payments = record.get('payment_details', [])
                combined_payments = existing_payments + new_payments
                update_data['payment_details'] = combined_payments

            update_data['updated_at'] = datetime.now()
            update_data = convert_dates_to_strings(update_data)

            if update_data:
                update_result = collection.update_one(
                    {"_id": object_id},
                    {"$set": update_data}
                )
                
                if update_result.modified_count > 0:
                    updated_record = collection.find_one({"_id": object_id})
                    updated_record['id'] = updated_record['_id']
                    del updated_record['_id']
                    
                    response_serializer = OtherRecordSerializer(updated_record)
                    return Response(response_serializer.data, status=status.HTTP_200_OK)
                else:
                    return Response({"message": "No changes made"}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'No valid fields to update'}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        if 'client' in locals():
            client.close()