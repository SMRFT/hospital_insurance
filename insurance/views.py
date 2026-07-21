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
from django.utils import timezone
from django.http import JsonResponse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods
from bson import ObjectId
from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.tokens import RefreshToken
from pymongo import MongoClient
from datetime import datetime, timedelta
from pyauth.auth import HasRolePermission
from dotenv import load_dotenv
import logging
from django.db.models import Q
logger = logging.getLogger(__name__)
load_dotenv()

from .models import Insurance , Daycare, OtherRecord
from .serializers import InsuranceSerializer , DaycareSerializer , OtherRecordSerializer

mongo_uri = os.getenv("GLOBAL_DB_HOST")

# Shared MongoClient pool to prevent socket leaks and latency
_mongo_client_pool = None

def get_mongo_client():
    global _mongo_client_pool
    if _mongo_client_pool is None:
        _mongo_client_pool = MongoClient(mongo_uri)
    return _mongo_client_pool

def get_insurance_db():
    return get_mongo_client()["Insurance"]

def get_global_db():
    return get_mongo_client()["Global"]

def get_er_billing_db():
    return get_mongo_client()["ER_Billing"]

# Insurance view
# views.py
@api_view(['GET', 'POST'])
@csrf_exempt
@permission_classes([HasRolePermission])
def insurance(request):
    try:
        db = get_insurance_db()
        fs = GridFS(db)

        # Extract employee_id from request header/body
        employee_id = (
            request.data.get('auth-user-id') or
            request.headers.get('auth-user-id') or
            "system"
        )

        if request.method == 'POST':
            data = request.data.copy()

            billing_file = request.FILES.get('billingFile')
            query_file = request.FILES.get('queryUpload')
            query_response_file = request.FILES.get('queryResponse')

            patient_uhid = data.get('patient_uhid', '').strip()
            patient_name = data.get('patient_name', '').strip()

            if any([billing_file, query_file, query_response_file]) and (not patient_uhid or not patient_name):
                return Response(
                    {"error": "patient_uhid and patient_name are required for file naming if uploading files"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Ensure date is consistent
            submission_date = data.get('date')
            if submission_date:
                try:
                    submission_date = datetime.strptime(submission_date, '%Y-%m-%d').date()
                except ValueError:
                    submission_date = datetime.now().date()
            else:
                submission_date = datetime.now().date()

            if patient_uhid:
                if Insurance.objects.filter(patient_uhid=patient_uhid, date=str(submission_date)).exists():
                    return Response(
                        {"error": f"This patient UHID ({patient_uhid}) for date {submission_date} is already stored."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Save files in GridFS
            try:
                if billing_file:
                    data['billingFile'] = str(fs.put(billing_file, filename=f"{patient_uhid}_{patient_name}_billing"))
                if query_file:
                    data['queryUpload'] = str(fs.put(query_file, filename=f"{patient_uhid}_{patient_name}_query"))
                if query_response_file:
                    data['queryResponse'] = str(fs.put(query_response_file, filename=f"{patient_uhid}_{patient_name}_queryresponse"))
            except Exception as gridfs_error:
                return Response(
                    {"error": "File upload failed", "details": str(gridfs_error)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # OP handling
            if data.get('opNumber') and not data.get('ipNumber'):
                data['opNumber'] = patient_uhid

            # Inject audit fields
            data['created_by'] = employee_id
            data['lastmodified_by'] = employee_id

            # Convert to plain dict (remove QueryDict issues)
            clean_data = {k: (str(v) if not isinstance(v, (list, dict)) else v) for k, v in data.items()}

            serializer = InsuranceSerializer(data=clean_data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)

            return Response({"error": "Invalid data", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        elif request.method == 'GET':
            collection = db["insurance_insurance"]
            query = {}

            company_name = request.GET.get('companyName')
            if company_name:
                query["companyName"] = company_name

            from_date = request.GET.get('from_date')
            to_date = request.GET.get('to_date')

            if from_date or to_date:
                date_query = {}
                if from_date:
                    date_query["$gte"] = from_date
                if to_date:
                    date_query["$lte"] = to_date
                if date_query:
                    query["date"] = date_query

            search_field = request.GET.get('search_field')
            search_value = request.GET.get('search_value')

            if search_field and search_value:
                if search_field in ['billNumber', 'ipNumber', 'opNumber', 'patient_name']:
                    query[search_field] = {"$regex": search_value, "$options": "i"}
                elif search_field == 'dateOfDischarge':
                    query["dateOfDischarge"] = search_value

            cursor = collection.find(query).sort([("date", -1), ("id", -1)])
            
            data_list = []
            for doc in cursor:
                doc.pop('_id', None)
                data_list.append(doc)
            # Resolve editHistory edited_by IDs to names
            global_db = get_global_db()
            for record in data_list:
                raw_history = record.get('editHistory')
                if isinstance(raw_history, str):
                    try:
                        import json as _json
                        raw_history = _json.loads(raw_history)
                    except Exception:
                        raw_history = []
                if isinstance(raw_history, list):
                    for h in raw_history:
                        emp_id = str(h.get('edited_by', ''))
                        if emp_id:
                            h['edited_by_name'] = get_employee_name_by_id(emp_id, db=global_db)
                    record['editHistory'] = raw_history
            return Response(data_list, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": "An error occurred", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



from bson import ObjectId
from django.http import HttpResponse, Http404
from pymongo import MongoClient
from gridfs import GridFS
import mimetypes

@api_view(['GET'])
@csrf_exempt
@permission_classes([HasRolePermission])
def serve_file(request, file_id):
    db = get_insurance_db()
    fs = GridFS(db)

    try:
        file_id = ObjectId(file_id)
        file = fs.get(file_id)

        # Step 1: Check if contentType stored in GridFS metadata
        content_type = getattr(file, "content_type", None)

        # Step 2: Try mimetypes from filename if not found
        if not content_type:
            content_type, _ = mimetypes.guess_type(file.filename)

        # Step 3: Default fallback
        if not content_type:
            content_type = "application/octet-stream"

        response = HttpResponse(file.read(), content_type=content_type)

        # Inline view (open in browser if possible)
        response['Content-Disposition'] = f'inline; filename="{file.filename}"'

        return response

    except Exception as e:
        raise Http404(f"File not found: {str(e)}")

    
    
@api_view(['POST', 'GET'])
@csrf_exempt
@permission_classes([HasRolePermission])
def submit_daycare(request):
    # Connect to the MongoDB instance
    db = get_insurance_db()
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
@permission_classes([HasRolePermission])
def insurance_update_combined(request, identifier):
    try:
        logger.info(f"Attempting to update record with identifier: {identifier}")
        if hasattr(request.data, 'dict'):
            data = request.data.dict()
        else:
            data = request.data.copy()
            
        # Strip auth fields injected by middleware
        data = {k: v for k, v in data.items() if not k.startswith("auth-")}
        # Normalize date
        update_date = data.get("date")
        if update_date:
            try:
                parsed_date = datetime.strptime(update_date, "%Y-%m-%d").date()
            except ValueError:
                return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)
        else:
            return Response({"error": "Date is required for update."}, status=400)

        # Connect to MongoDB GridFS and DB
        db = get_insurance_db()
        fs = GridFS(db)
        collection = db["insurance_insurance"]

        # Identify the insurance object using PyMongo
        insurance = None
        date_str = str(parsed_date)
        
        if identifier.isdigit():
            insurance = collection.find_one({"id": int(identifier)})
            
        if not insurance:
            if identifier.upper().startswith("OP"):
                insurance = collection.find_one({"opNumber": identifier, "date": date_str})
            elif identifier.upper().startswith("IP"):
                insurance = collection.find_one({"ipNumber": identifier, "date": date_str})
            else:
                insurance = collection.find_one({"billNumber": identifier, "date": date_str})
                if not insurance:
                    insurance = collection.find_one({"opNumber": {"$regex": f"{identifier}$"}, "date": date_str})
                if not insurance:
                    insurance = collection.find_one({"ipNumber": {"$regex": f"{identifier}$"}, "date": date_str})

        if not insurance:
            return Response({"error": f"No record found for identifier {identifier} and date {update_date}"}, status=404)

        # File handling
        patient_uhid = data.get("patient_uhid", insurance.get("patient_uhid", "")).strip()
        patient_name = data.get("patient_name", insurance.get("patient_name", "")).strip()

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
            elif insurance.get(file_field):
                data[file_field] = insurance.get(file_field)

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
                    clean_json = edit_history_json
                    if clean_json.startswith('"') and clean_json.endswith('"'):
                        clean_json = clean_json[1:-1]
                    clean_json = clean_json.replace('\\"', '"')
                    edit_history = json.loads(clean_json)
                elif isinstance(edit_history_json, list):
                    edit_history = edit_history_json
                
                data["editHistory"] = edit_history
            except Exception as e:
                logger.error(f"Failed to parse editHistory: {e}")
                return Response({"error": "Failed to parse edit history"}, status=400)

        # Ensure _id is not in the data to avoid conflicts
        if '_id' in data:
            del data['_id']

        # 🔹 Set lastmodified_by from auth-user-id (or fallback system)
        employee_id = (
            request.data.get('auth-user-id') or
            request.headers.get('auth-user-id') or
            "system"
        )
        data["lastmodified_by"] = employee_id
        data["lastmodified_date"] = timezone.now()
        
        # Use PyMongo for update to preserve arrays (like editHistory) and prevent Djongo duplicates
        collection = db["insurance_insurance"]
        
        # Remove fields we don't want to accidentally override
        if 'id' in data:
            del data['id']
            
        insurance_id = insurance.get('id')
        collection.update_one({"id": insurance_id}, {"$set": data})
        
        return Response({
            "message": "Insurance updated successfully",
            "data": {"id": insurance_id, **data}
        }, status=200)

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
@csrf_exempt
@permission_classes([HasRolePermission])
def get_insurance_companies(request):
    try:
        # MongoDB connection
        db = get_insurance_db()
        collection = db["insurance_company"]

        # Fetch all documents
        insurance_companies = list(collection.find({}, {"_id": 0}))  # Exclude _id from response

        return JsonResponse(insurance_companies, safe=False, status=200)

    except Exception as e:
        return JsonResponse({"error": "Failed to fetch insurance companies", "details": str(e)}, status=500)


# Helper function to convert dates to strings
def convert_dates_to_strings(data):
    if isinstance(data, dict):
        return {k: convert_dates_to_strings(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_dates_to_strings(item) for item in data]
    elif isinstance(data, datetime):
        return data.isoformat()
    else:
        return data


def get_employee_name_by_id(employee_id, db=None, cache=None):
    """Get employee name from Global database by employee ID, with connection reuse and optional caching"""
    if employee_id is None:
        return ""
    employee_id_str = str(employee_id).strip()
    if not employee_id_str:
        return ""

    if cache is not None and employee_id_str in cache:
        return cache[employee_id_str]

    try:
        if db is None:
            db = get_global_db()
        collection = db["backend_diagnostics_profile"]
        
        employee = collection.find_one({"employeeId": employee_id_str})
        
        name = employee.get('employeeName', employee_id_str) if employee else employee_id_str
        if cache is not None:
            cache[employee_id_str] = name
        return name
    except Exception as e:
        logger.error(f"Error fetching employee name for {employee_id_str}: {str(e)}")
        return employee_id_str


def check_previous_day_final_approval(collection, record_date):
    """Check if previous day records are all final approved"""
    try:
        record_date_obj = datetime.strptime(record_date, '%Y-%m-%d').date()
        previous_date = (record_date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Find all records from previous day
        previous_records = list(collection.find({
            'date': previous_date
        }))
        
        if not previous_records:
            # No records on previous day, so allow approval
            return True, None
        
        # Check if any record is not final approved
        for record in previous_records:
            if not record.get('is_finalapproved', False):
                return False, previous_date
        
        return True, None
    except Exception as e:
        print(f"Error checking previous day approval: {str(e)}")
        return True, None  # In case of error, allow the operation
    
    
AUTH_FIELDS = [
    'auth-user-id',
    'auth-user-name',
    'auth-user-email',
    'auth-branch-code',
    'auth-page-id',
    'auth-action-id',
    'auth-permission-id',
    'auth-allowed-action-codes',
    'auth-allowed-branch-codes',
    'auth-hospital-code'
]

@api_view(['GET', 'POST', 'PUT'])
@csrf_exempt
@permission_classes([HasRolePermission])
def other_record_view(request):
    """
    GET: Fetch all records (filtered by status if specified)
    POST: Create new record with 'Pending' status
    PUT: Update record including status changes and approved_by
    """
    try:
        db = get_insurance_db()
        collection = db["insurance_otherrecord"]

        # Get employee ID from request
        employee_id = (
            request.data.get('auth-user-id')
            or request.headers.get('auth-user-id')
            or "system"
        )

        if request.method == 'GET':
            from_date = request.GET.get('from_date')
            to_date = request.GET.get('to_date')
            status_filter = request.GET.get('status')

            query = {}
            
            if status_filter:
                query['status'] = status_filter

            records = list(collection.find(query))
            processed_records = []

            # Bulk fetch unique employee names in a single query
            employee_ids = set()
            for record in records:
                for field in ['created_by', 'approved_by', 'final_approved_by', 'refund_approved_by', 'refund_initiated_by']:
                    val = record.get(field)
                    if val:
                        employee_ids.add(str(val).strip())
            
            name_cache = {}
            global_db = get_global_db()
            if employee_ids:
                try:
                    profile_col = global_db["backend_diagnostics_profile"]
                    profiles = list(profile_col.find({"employeeId": {"$in": list(employee_ids)}}))
                    for p in profiles:
                        emp_id = str(p.get("employeeId")).strip()
                        name_cache[emp_id] = p.get("employeeName", emp_id)
                except Exception as ex:
                    logger.error(f"Error bulk fetching employee names in other_record_view: {ex}")

            for record in records:
                if record.get('payment_details'):
                    filtered_payments = []
                    for payment in record['payment_details']:
                        payment_date = payment.get('date', '')

                        if not payment_date:
                            continue
                        if from_date and payment_date < from_date:
                            continue
                        if to_date and payment_date > to_date:
                            continue

                        filtered_payments.append(payment)

                    if filtered_payments:
                        record_copy = record.copy()
                        record_copy['payment_details'] = filtered_payments
                        
                        # Get employee names for display
                        if record_copy.get('created_by'):
                            record_copy['created_by_name'] = get_employee_name_by_id(record_copy['created_by'], db=global_db, cache=name_cache)
                        if record_copy.get('approved_by'):
                            record_copy['approved_by_name'] = get_employee_name_by_id(record_copy['approved_by'], db=global_db, cache=name_cache)
                        if record_copy.get('final_approved_by'):
                            record_copy['final_approved_by_name'] = get_employee_name_by_id(record_copy['final_approved_by'], db=global_db, cache=name_cache)
                        if record_copy.get('refund_approved_by'):
                            record_copy['refund_approved_by_name'] = get_employee_name_by_id(record_copy['refund_approved_by'], db=global_db, cache=name_cache)
                        if record_copy.get('refund_initiated_by'):
                            record_copy['refund_initiated_by_name'] = get_employee_name_by_id(record_copy['refund_initiated_by'], db=global_db, cache=name_cache)

                        # Resolve editHistory edited_by IDs to names
                        raw_history = record_copy.get('editHistory')
                        if isinstance(raw_history, str):
                            try:
                                raw_history = json.loads(raw_history)
                            except Exception:
                                raw_history = []
                        if isinstance(raw_history, list):
                            for h in raw_history:
                                emp_id = str(h.get('edited_by', ''))
                                if emp_id:
                                    h['edited_by_name'] = get_employee_name_by_id(emp_id, db=global_db, cache=name_cache)
                            record_copy['editHistory'] = raw_history

                        processed_records.append(record_copy)

            for record in processed_records:
                record['id'] = str(record['_id'])
                del record['_id']

            return Response(processed_records, status=status.HTTP_200_OK)

        elif request.method == 'POST':
            validated_data = {
                k: v for k, v in request.data.items()
                if k not in AUTH_FIELDS
            }

            required_fields = ['patient_uhid', 'patient_name', 'company_name', 'treatment']
            for field in required_fields:
                if not validated_data.get(field):
                    return Response({'error': f'{field.replace("_", " ").title()} is mandatory'}, status=status.HTTP_400_BAD_REQUEST)
            
            payment_details = validated_data.get('payment_details', [])
            if not payment_details or len(payment_details) == 0:
                return Response({'error': 'At least one Payment Detail is mandatory'}, status=status.HTTP_400_BAD_REQUEST)

            
            # Set default status and approval flags
            validated_data['status'] = 'Pending'
            validated_data['is_approved'] = False
            validated_data['is_finalapproved'] = False
            validated_data['is_refund_approved'] = False
            
            # Set timestamps
            validated_data['created_date'] = datetime.now().isoformat()
            validated_data['lastmodified_date'] = datetime.now().isoformat()
            validated_data['created_by'] = employee_id
            validated_data['lastmodified_by'] = employee_id
            
            # Ensure has_refund is properly stored as boolean
            if 'has_refund' in validated_data:
                validated_data['has_refund'] = bool(validated_data['has_refund'])
            else:
                validated_data['has_refund'] = False
            
            # Ensure refund amount is stored correctly
            if 'refund' not in validated_data or validated_data['refund'] == '':
                validated_data['refund'] = '0'

            validated_data = convert_dates_to_strings(validated_data)

            result = collection.insert_one(validated_data)
            created_record = collection.find_one({'_id': result.inserted_id})
            created_record['id'] = str(created_record['_id'])
            del created_record['_id']

            return Response(created_record, status=status.HTTP_201_CREATED)

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

            new_status = request.data.get('status')
            
            # Check if trying to approve/collect/issue gate pass
            if new_status in ['Approved', 'Collected', 'Gate Pass Issued']:
                record_date = record.get('date')
                if record_date:
                    # Check if previous day is final approved
                    is_allowed, previous_date = check_previous_day_final_approval(collection, record_date)
                    if not is_allowed:
                        return Response({
                            'error': f'Not Final Approved for {previous_date}',
                            'message': f'Previous day ({previous_date}) records must be final approved before updating this record'
                        }, status=status.HTTP_400_BAD_REQUEST)

            required_fields = ['patient_uhid', 'patient_name', 'company_name', 'treatment']
            for field in required_fields:
                if not request.data.get(field):
                    return Response({'error': f'{field.replace("_", " ").title()} is mandatory'}, status=status.HTTP_400_BAD_REQUEST)
            
            payment_details = request.data.get('payment_details', record.get('payment_details', []))
            if not payment_details or len(payment_details) == 0:
                return Response({'error': 'At least one Payment Detail is mandatory'}, status=status.HTTP_400_BAD_REQUEST)

            update_data = {}
            
            # Basic fields that can be updated
            basic_fields = [
                'date', 'patient_name', 'patient_uhid', 'mobile_number',
                'ip_op_type', 'doctor_name', 'company_name', 'treatment', 
                'refund', 'status', 'has_refund', 'specificInsuranceCompany',
                'is_refund_initiated'
            ]

            for field in basic_fields:
                if field in request.data:
                    if field == 'has_refund':
                        update_data[field] = bool(request.data[field])
                    elif field == 'refund':
                        update_data[field] = str(request.data[field]) if request.data[field] else '0'
                    else:
                        update_data[field] = request.data[field]

            # Handle payment_details update
            if 'payment_details' in request.data:
                update_data['payment_details'] = request.data['payment_details']

            # Handle editHistory — parse if JSON string, store as array
            if 'editHistory' in request.data:
                history_raw = request.data['editHistory']
                if isinstance(history_raw, str):
                    try:
                        history_raw = json.loads(history_raw)
                    except Exception:
                        history_raw = []
                update_data['editHistory'] = history_raw if isinstance(history_raw, list) else []
            
            # Handle status change to 'Approved'
            if new_status == 'Approved':
                if not record.get('is_approved', False):
                    update_data['is_approved'] = True
                    update_data['approved_by'] = employee_id
                    update_data['approved_date'] = datetime.now().isoformat()
                    
            # Handle refund initiated
            if update_data.get('is_refund_initiated') and not record.get('is_refund_initiated', False):
                update_data['refund_initiated_by'] = employee_id
                update_data['refund_initiated_date'] = datetime.now().isoformat()

            # Set last modified info
            update_data['lastmodified_date'] = datetime.now().isoformat()
            update_data['lastmodified_by'] = employee_id
            
            update_data = convert_dates_to_strings(update_data)

            if update_data:
                update_result = collection.update_one(
                     {"_id": object_id},
                     {"$set": update_data}
                )

                if update_result.modified_count > 0:
                    updated_record = collection.find_one({"_id": object_id})
                    
                    # Get employee names for display
                    global_db = get_global_db()
                    if updated_record.get('approved_by'):
                        updated_record['approved_by_name'] = get_employee_name_by_id(updated_record['approved_by'], db=global_db)
                    if updated_record.get('final_approved_by'):
                        updated_record['final_approved_by_name'] = get_employee_name_by_id(updated_record['final_approved_by'], db=global_db)
                    if updated_record.get('refund_approved_by'):
                        updated_record['refund_approved_by_name'] = get_employee_name_by_id(updated_record['refund_approved_by'], db=global_db)
                    
                    updated_record['id'] = str(updated_record['_id'])
                    del updated_record['_id']

                    return Response(updated_record, status=status.HTTP_200_OK)
                else:
                    return Response({"message": "No changes made"}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'No valid fields to update'}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@csrf_exempt
@permission_classes([HasRolePermission])
def other_record_report_view(request):
    """
    Get flattened report data - ALL records with all statuses
    Each payment entry becomes a separate row
    """
    try:
        db = get_insurance_db()
        collection = db["insurance_otherrecord"]
        
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        
        # Get ALL records regardless of status
        records = list(collection.find({}))
        flattened_data = []

        # Bulk fetch unique employee names in a single query
        employee_ids = set()
        for record in records:
            for field in ['created_by', 'approved_by', 'final_approved_by', 'refund_approved_by', 'refund_initiated_by']:
                val = record.get(field)
                if val:
                    employee_ids.add(str(val).strip())
        
        name_cache = {}
        global_db = get_global_db()
        if employee_ids:
            try:
                profile_col = global_db["backend_diagnostics_profile"]
                profiles = list(profile_col.find({"employeeId": {"$in": list(employee_ids)}}))
                for p in profiles:
                    emp_id = str(p.get("employeeId")).strip()
                    name_cache[emp_id] = p.get("employeeName", emp_id)
            except Exception as ex:
                logger.error(f"Error bulk fetching employee names in other_record_report_view: {ex}")
        
        for record in records:
            if record.get('payment_details'):
                for payment in record['payment_details']:
                    payment_date = payment.get('date', '')
                    
                    if not payment_date:
                        continue
                    
                    if from_date and payment_date < from_date:
                        continue
                    if to_date and payment_date > to_date:
                        continue
                    
                    flat_record = {
                        'id': str(record['_id']),
                        'date': payment_date,
                        'ip_op_type': record.get('ip_op_type', ''),
                        'patient_name': record.get('patient_name', ''),
                        'patient_uhid': record.get('patient_uhid', ''),
                        'mobile_number': record.get('mobile_number', ''),
                        'doctor_name': record.get('doctor_name', ''),
                        'company_name': record.get('company_name', ''),
                        'specificInsuranceCompany': record.get('specificInsuranceCompany', ''),
                        'treatment': record.get('treatment', ''),
                        'amount': payment.get('amount', 0),
                        'payment_method': payment.get('payment_method', ''),
                        'upi_details': payment.get('upi_details', ''),
                        'payment_details': record.get('payment_details', []),
                        'has_refund': record.get('has_refund', False),
                        'refund': record.get('refund', 0),
                        'is_refund_initiated': record.get('is_refund_initiated', False),
                        'refund_initiated_by': record.get('refund_initiated_by', ''),
                        'refund_initiated_date': record.get('refund_initiated_date', ''),
                        'status': record.get('status', 'Pending'),
                        'is_approved': record.get('is_approved', False),
                        'approved_by': record.get('approved_by', ''),
                        'approved_date': record.get('approved_date', ''),
                        'is_finalapproved': record.get('is_finalapproved', False),
                        'final_approved_by': record.get('final_approved_by', ''),
                        'final_approved_date': record.get('final_approved_date', ''),
                        'is_refund_approved': record.get('is_refund_approved', False),
                        'refund_approved_by': record.get('refund_approved_by', ''),
                        'refund_approved_date': record.get('refund_approved_date', ''),
                        'created_by': record.get('created_by', ''),
                        'editHistory': record.get('editHistory', []),
                    }
                    
                    # Get employee names for display
                    if flat_record['created_by']:
                        flat_record['created_by_name'] = get_employee_name_by_id(flat_record['created_by'], db=global_db, cache=name_cache)
                    if flat_record['approved_by']:
                        flat_record['approved_by_name'] = get_employee_name_by_id(flat_record['approved_by'], db=global_db, cache=name_cache)
                    if flat_record['final_approved_by']:
                        flat_record['final_approved_by_name'] = get_employee_name_by_id(flat_record['final_approved_by'], db=global_db, cache=name_cache)
                    if flat_record['refund_approved_by']:
                        flat_record['refund_approved_by_name'] = get_employee_name_by_id(flat_record['refund_approved_by'], db=global_db, cache=name_cache)
                    if flat_record['refund_initiated_by']:
                        flat_record['refund_initiated_by_name'] = get_employee_name_by_id(flat_record['refund_initiated_by'], db=global_db, cache=name_cache)
                    # Resolve editHistory edited_by IDs to names
                    raw_history = flat_record.get('editHistory')
                    if isinstance(raw_history, str):
                        try:
                            raw_history = json.loads(raw_history)
                        except Exception:
                            raw_history = []
                    if isinstance(raw_history, list):
                        for h in raw_history:
                            emp_id = str(h.get('edited_by', ''))
                            if emp_id:
                                h['edited_by_name'] = get_employee_name_by_id(emp_id, db=global_db, cache=name_cache)
                        flat_record['editHistory'] = raw_history

                    flattened_data.append(flat_record)
        
        flattened_data.sort(key=lambda x: x['date'], reverse=True)
        
        return Response(flattened_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@csrf_exempt
@permission_classes([HasRolePermission])
def collected_finalapproved_view(request):
    """
    GET: Fetch all records with 'Final Approved'
    """
    try:
        db = get_insurance_db()
        collection = db["insurance_otherrecord"]
        
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        
        # Get records with 'Final Approved' 
        records = list(collection.find({
            'status': 'Final Approved',
            'is_finalapproved': True
        }))

        # Bulk fetch unique employee names in a single query
        employee_ids = set()
        for record in records:
            for field in ['created_by', 'approved_by', 'final_approved_by']:
                val = record.get(field)
                if val:
                    employee_ids.add(str(val).strip())
        
        name_cache = {}
        global_db = get_global_db()
        if employee_ids:
            try:
                profile_col = global_db["backend_diagnostics_profile"]
                profiles = list(profile_col.find({"employeeId": {"$in": list(employee_ids)}}))
                for p in profiles:
                    emp_id = str(p.get("employeeId")).strip()
                    name_cache[emp_id] = p.get("employeeName", emp_id)
            except Exception as ex:
                logger.error(f"Error bulk fetching employee names in collected_finalapproved_view: {ex}")
        
        approval_data = []
        
        for record in records:
            if record.get('payment_details'):
                for payment in record['payment_details']:
                    payment_date = payment.get('date', '')
                    
                    if not payment_date:
                        continue
                    
                    if from_date and payment_date < from_date:
                        continue
                    if to_date and payment_date > to_date:
                        continue
                    
                    flat_record = {
                        'id': str(record['_id']),
                        'date': payment_date,
                        'patient_name': record.get('patient_name', ''),
                        'patient_uhid': record.get('patient_uhid', ''),
                        'mobile_number': record.get('mobile_number', ''),
                        'doctor_name': record.get('doctor_name', ''),
                        'company_name': record.get('company_name', ''),
                        'treatment': record.get('treatment', ''),
                        'amount': payment.get('amount', 0),
                        'payment_method': payment.get('payment_method', ''),
                        'has_refund': record.get('has_refund', False),
                        'refund': record.get('refund', 0),
                        'status': record.get('status', ''),
                        'is_approved': record.get('is_approved', False),
                        'approved_by': record.get('approved_by', ''),
                        'approved_date': record.get('approved_date', ''),
                        'is_finalapproved': record.get('is_finalapproved', False),
                        'final_approved_by': record.get('final_approved_by', ''),
                        'final_approved_date': record.get('final_approved_date', ''),
                        'created_by': record.get('created_by', ''),
                    }
                    
                    # Get employee names for display
                    if flat_record['created_by']:
                        flat_record['created_by_name'] = get_employee_name_by_id(flat_record['created_by'], db=global_db, cache=name_cache)
                    if flat_record['approved_by']:
                        flat_record['approved_by_name'] = get_employee_name_by_id(flat_record['approved_by'], db=global_db, cache=name_cache)
                    if flat_record['final_approved_by']:
                        flat_record['final_approved_by_name'] = get_employee_name_by_id(flat_record['final_approved_by'], db=global_db, cache=name_cache)
                    
                    approval_data.append(flat_record)
        
        approval_data.sort(key=lambda x: x['date'], reverse=True)
        
        return Response(approval_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@csrf_exempt
@permission_classes([HasRolePermission])
def overall_approval_view(request):
    """
    GET: Fetch all records with 'Gate Pass Issued' status that are NOT yet final approved
    """
    try:
        db = get_insurance_db()
        collection = db["insurance_otherrecord"]
        
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        
        # Get records with 'Gate Pass Issued' status that are NOT final approved
        records = list(collection.find({
            'status': 'Collected',
            'is_approved': True
        }))

        # Bulk fetch unique employee names in a single query
        employee_ids = set()
        for record in records:
            for field in ['created_by', 'approved_by', 'final_approved_by']:
                val = record.get(field)
                if val:
                    employee_ids.add(str(val).strip())
        
        name_cache = {}
        global_db = get_global_db()
        if employee_ids:
            try:
                profile_col = global_db["backend_diagnostics_profile"]
                profiles = list(profile_col.find({"employeeId": {"$in": list(employee_ids)}}))
                for p in profiles:
                    emp_id = str(p.get("employeeId")).strip()
                    name_cache[emp_id] = p.get("employeeName", emp_id)
            except Exception as ex:
                logger.error(f"Error bulk fetching employee names in overall_approval_view: {ex}")
        
        approval_data = []
        
        for record in records:
            if record.get('payment_details'):
                for payment in record['payment_details']:
                    payment_date = payment.get('date', '')
                    
                    if not payment_date:
                        continue
                    
                    if from_date and payment_date < from_date:
                        continue
                    if to_date and payment_date > to_date:
                        continue
                    
                    flat_record = {
                        'id': str(record['_id']),
                        'date': payment_date,
                        'patient_name': record.get('patient_name', ''),
                        'patient_uhid': record.get('patient_uhid', ''),
                        'mobile_number': record.get('mobile_number', ''),
                        'doctor_name': record.get('doctor_name', ''),
                        'company_name': record.get('company_name', ''),
                        'treatment': record.get('treatment', ''),
                        'amount': payment.get('amount', 0),
                        'payment_method': payment.get('payment_method', ''),
                        'has_refund': record.get('has_refund', False),
                        'refund': record.get('refund', 0),
                        'status': record.get('status', ''),
                        'created_by': record.get('created_by', ''),
                        'is_approved': record.get('is_approved', False),
                        'approved_by': record.get('approved_by', ''),
                        'approved_date': record.get('approved_date', ''),
                        'is_finalapproved': record.get('is_finalapproved', False),
                        'final_approved_by': record.get('final_approved_by', ''),
                        'final_approved_date': record.get('final_approved_date', '')
                    }
                    
                    # Get employee names for display
                    if flat_record['created_by']:
                        flat_record['created_by_name'] = get_employee_name_by_id(flat_record['created_by'], db=global_db, cache=name_cache)
                    if flat_record['approved_by']:
                        flat_record['approved_by_name'] = get_employee_name_by_id(flat_record['approved_by'], db=global_db, cache=name_cache)
                    if flat_record['final_approved_by']:
                        flat_record['final_approved_by_name'] = get_employee_name_by_id(flat_record['final_approved_by'], db=global_db, cache=name_cache)
                    
                    approval_data.append(flat_record)
        
        approval_data.sort(key=lambda x: x['date'], reverse=True)
        
        return Response(approval_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@csrf_exempt
@permission_classes([HasRolePermission])
def final_approval_view(request):
    """
    POST: Update final_approved_by and final_approved_date for records with status 'Gate Pass Issued'
    """
    try:
        db = get_insurance_db()
        collection = db["insurance_otherrecord"]

        # Get employee ID from request
        employee_id = (
            request.data.get('auth-user-id')
            or request.headers.get('auth-user-id')
            or "system"
        )

        record_ids = request.data.get('record_ids', [])
        
        if not record_ids:
            return Response({'error': 'No record IDs provided'}, status=status.HTTP_400_BAD_REQUEST)

        updated_count = 0
        
        for record_id in record_ids:
            try:
                if isinstance(record_id, dict) and '$oid' in record_id:
                    object_id = ObjectId(record_id['$oid'])
                elif isinstance(record_id, str):
                    object_id = ObjectId(record_id)
                else:
                    object_id = ObjectId(record_id)
            except Exception as e:
                continue

            update_data = {
                'status': "Final Approved",
                'is_finalapproved': True,
                'final_approved_by': employee_id,
                'final_approved_date': datetime.now().isoformat(),
                'lastmodified_date': datetime.now().isoformat(),
                'lastmodified_by': employee_id
            }

            update_result = collection.update_one(
                {"_id": object_id},
                {"$set": update_data}
            )

            if update_result.modified_count > 0:
                updated_count += 1

        return Response({
            'message': f'{updated_count} record(s) final approved successfully',
            'updated_count': updated_count
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@csrf_exempt
@permission_classes([HasRolePermission])
def refund_approval_view(request):
    """
    GET: Fetch all records with refund amount that are NOT yet refund approved
    """
    try:
        db = get_insurance_db()
        collection = db["insurance_otherrecord"]
        
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        
        # Get records with has_refund = True that are NOT refund approved
        records = list(collection.find({
            'has_refund': True,
            'is_refund_approved': {'$ne': True}
        }))

        # Bulk fetch unique employee names in a single query
        employee_ids = set()
        for record in records:
            val = record.get('refund_approved_by')
            if val:
                employee_ids.add(str(val).strip())
        
        name_cache = {}
        global_db = get_global_db()
        if employee_ids:
            try:
                profile_col = global_db["backend_diagnostics_profile"]
                profiles = list(profile_col.find({"employeeId": {"$in": list(employee_ids)}}))
                for p in profiles:
                    emp_id = str(p.get("employeeId")).strip()
                    name_cache[emp_id] = p.get("employeeName", emp_id)
            except Exception as ex:
                logger.error(f"Error bulk fetching employee names in refund_approval_view: {ex}")
        
        refund_data = []
        
        for record in records:
            if record.get('payment_details'):
                for payment in record['payment_details']:
                    payment_date = payment.get('date', '')
                    
                    if not payment_date:
                        continue
                    
                    if from_date and payment_date < from_date:
                        continue
                    if to_date and payment_date > to_date:
                        continue
                    
                    flat_record = {
                        'id': str(record['_id']),
                        'date': payment_date,
                        'patient_name': record.get('patient_name', ''),
                        'patient_uhid': record.get('patient_uhid', ''),
                        'mobile_number': record.get('mobile_number', ''),
                        'company_name': record.get('company_name', ''),
                        'treatment': record.get('treatment', ''),
                        'amount': payment.get('amount', 0),
                        'payment_method': payment.get('payment_method', ''),
                        'refund': record.get('refund', 0),
                        'status': record.get('status', ''),
                        'is_refund_approved': record.get('is_refund_approved', False),
                        'refund_approved_by': record.get('refund_approved_by', ''),
                        'refund_approved_date': record.get('refund_approved_date', '')
                    }
                    
                    # Get employee names for display
                    if flat_record['refund_approved_by']:
                        flat_record['refund_approved_by_name'] = get_employee_name_by_id(flat_record['refund_approved_by'], db=global_db, cache=name_cache)
                    
                    refund_data.append(flat_record)
        
        refund_data.sort(key=lambda x: x['date'], reverse=True)
        
        return Response(refund_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@csrf_exempt
@permission_classes([HasRolePermission])
def refund_approval_update_view(request):
    """
    PUT: Update refund_approved_by and refund_approved_date for records with refund amount
    """
    try:
        db = get_insurance_db()
        collection = db["insurance_otherrecord"]

        # Get employee ID from request
        employee_id = (
            request.data.get('auth-user-id')
            or request.headers.get('auth-user-id')
            or "system"
        )

        record_ids = request.data.get('record_ids', [])
        
        if not record_ids:
            return Response({'error': 'No record IDs provided'}, status=status.HTTP_400_BAD_REQUEST)

        updated_count = 0
        
        for record_id in record_ids:
            try:
                if isinstance(record_id, dict) and '$oid' in record_id:
                    object_id = ObjectId(record_id['$oid'])
                elif isinstance(record_id, str):
                    object_id = ObjectId(record_id)
                else:
                    object_id = ObjectId(record_id)
            except Exception as e:
                continue

            update_data = {
                'is_refund_approved': True,
                'refund_approved_by': employee_id,
                'refund_approved_date': datetime.now().isoformat(),
                'lastmodified_date': datetime.now().isoformat(),
                'lastmodified_by': employee_id
            }

            update_result = collection.update_one(
                {"_id": object_id},
                {"$set": update_data}
            )

            if update_result.modified_count > 0:
                updated_count += 1

        return Response({
            'message': f'{updated_count} refund(s) approved successfully',
            'updated_count': updated_count
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@csrf_exempt
@permission_classes([HasRolePermission])
def get_doctor_list(request):
    db = get_er_billing_db()
    collection = db["doctors_list"]

    doctors = list(collection.find({"is_active": True}, {"_id": 0}))
    return JsonResponse(doctors, safe=False)


@api_view(['GET'])
@csrf_exempt
@permission_classes([HasRolePermission])
def get_treatment_list(request):
    db = get_insurance_db()
    collection = db["treatment_list"] 

    treatments = list(collection.find({"is_active": True}, {"_id": 0}))
    return JsonResponse(treatments, safe=False)


@api_view(['POST'])
@csrf_exempt
@permission_classes([HasRolePermission])
def add_doctor(request):
    try:
        data = request.data

        db = get_er_billing_db()
        collection = db["doctors_list"]

        # Get employee ID from request
        employee_id = (
            request.data.get('auth-user-id')
            or request.headers.get('auth-user-id')
            or "system"
        )

        doctor = {
            "doctor_name": data.get("doctor_name"),
            "department": data.get("department"),
            "is_active": True,
            "created_by": employee_id,
            "created_date": datetime.now()
        }

        collection.insert_one(doctor)

        return JsonResponse({"message": "Doctor added successfully"}, status=201)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)



@api_view(['POST'])
@csrf_exempt
@permission_classes([HasRolePermission])
def add_treatment(request):
    try:
        data = request.data

        db = get_insurance_db()
        collection = db["treatment_list"]

        # Get employee ID from request
        employee_id = (
            request.data.get('auth-user-id')
            or request.headers.get('auth-user-id')
            or "system"
        )

        treatment = {
            "id": data.get("id"),
            "name": data.get("name"),
            "is_active": True,
            "created_by": employee_id,
            "created_date": datetime.now()
        }

        collection.insert_one(treatment)

        return JsonResponse({"message": "Treatment added successfully"}, status=201)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
    

from .models import Enquiry, FollowUp
from .serializers import EnquirySerializer, FollowUpSerializer
# ─────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────

def _date_filtered_enquiries(request):
    """Return Enquiry queryset filtered by from_date / to_date query params."""
    qs = Enquiry.objects.prefetch_related(
        "follow_ups"
    ).order_by("-date", "-enquiry_id")

    from_date = request.query_params.get("from_date")
    to_date = request.query_params.get("to_date")

    if from_date:
        qs = qs.filter(date__gte=from_date)

    if to_date:
        qs = qs.filter(date__lte=to_date)

    return qs


def get_employee_id(request):
    return (
        request.data.get("auth-user-id")
        or request.headers.get("auth-user-id")
        or "system"
    )


# ─────────────────────────────────────────────────────────────
# ENQUIRY
# ─────────────────────────────────────────────────────────────

@api_view(["GET", "POST"])
@csrf_exempt
@permission_classes([HasRolePermission])
def enquiry_view(request):

    if request.method == "GET":
        enquiries = _date_filtered_enquiries(request)
        serializer = EnquirySerializer(enquiries, many=True)

        return Response({
            "success": True,
            "data": serializer.data
        })

    # POST
    employee_id = get_employee_id(request)
    print("Creating enquiry by employee:", employee_id)

    data = request.data

    data["created_by"] = employee_id
    data["created_date"] = timezone.now()

    serializer = EnquirySerializer(data=data)

    if serializer.is_valid():
        serializer.save()

        return Response(
            {
                "success": True,
                "message": "Enquiry created successfully",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(
        {
            "success": False,
            "errors": serializer.errors
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


# ─────────────────────────────────────────────────────────────
# ENQUIRY LIST
# ─────────────────────────────────────────────────────────────

@api_view(["GET"])
@csrf_exempt
@permission_classes([HasRolePermission])
def enquiry_list(request):

    enquiries = _date_filtered_enquiries(request)

    serializer = EnquirySerializer(
        enquiries,
        many=True
    )

    return Response({
        "success": True,
        "data": serializer.data
    })


# ─────────────────────────────────────────────────────────────
# FOLLOWUP LIST + CREATE
# ─────────────────────────────────────────────────────────────

@api_view(["GET", "POST"])
@csrf_exempt
@permission_classes([HasRolePermission])
def followup_view(request, enquiry_id):

    try:
        enquiry = Enquiry.objects.get(
            enquiry_id=enquiry_id
        )

    except Enquiry.DoesNotExist:
        return Response(
            {
                "success": False,
                "error": "Enquiry not found"
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":

        follow_ups = enquiry.follow_ups.all().order_by(
            "-followup_date"
        )

        serializer = FollowUpSerializer(
            follow_ups,
            many=True
        )

        return Response({
            "success": True,
            "data": serializer.data
        })

    # POST

    employee_id = get_employee_id(request)

    data = request.data.copy()

    data["enquiry"] = enquiry_id

    data["created_by"] = employee_id
    data["created_date"] = timezone.now()

    serializer = FollowUpSerializer(data=data)

    if serializer.is_valid():

        serializer.save()

        return Response(
            {
                "success": True,
                "message": "Follow-up created successfully",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(
        {
            "success": False,
            "errors": serializer.errors
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


# ─────────────────────────────────────────────────────────────
# FOLLOWUP DETAIL
# ─────────────────────────────────────────────────────────────

@api_view(["GET", "PUT", "DELETE"])
@csrf_exempt
@permission_classes([HasRolePermission])
def followup_detail_view(
    request,
    enquiry_id,
    followup_id
):

    try:
        enquiry = Enquiry.objects.get(
            enquiry_id=enquiry_id
        )

        follow_up = enquiry.follow_ups.get(
            followup_id=followup_id
        )

    except Enquiry.DoesNotExist:
        return Response(
            {
                "success": False,
                "error": "Enquiry not found"
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    except FollowUp.DoesNotExist:
        return Response(
            {
                "success": False,
                "error": "Follow-up not found"
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # GET

    if request.method == "GET":

        serializer = FollowUpSerializer(
            follow_up
        )

        return Response({
            "success": True,
            "data": serializer.data
        })

    # PUT

    elif request.method == "PUT":

        employee_id = get_employee_id(request)

        data = request.data.copy()

        data["enquiry"] = enquiry_id

        data["lastmodified_by"] = employee_id
        data["lastmodified_date"] = timezone.now()

        serializer = FollowUpSerializer(
            follow_up,
            data=data,
            partial=True
        )

        if serializer.is_valid():

            serializer.save()

            return Response(
                {
                    "success": True,
                    "message": "Follow-up updated successfully",
                    "data": serializer.data,
                }
            )

        return Response(
            {
                "success": False,
                "errors": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # DELETE

    elif request.method == "DELETE":

        follow_up.delete()

        return Response(
            {
                "success": True,
                "message": "Follow-up deleted successfully"
            }
        )

# ─────────────────────────────────────────────────────────────
# RT AND CHEMO RECORDS
# ─────────────────────────────────────────────────────────────
from .models import RTRecord, ChemoRecord
from .serializers import RTRecordSerializer, ChemoRecordSerializer

@api_view(["GET", "POST"])
@csrf_exempt
@permission_classes([HasRolePermission])
def rt_record_view(request):
    if request.method == "GET":
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        db = get_insurance_db()
        collection = db["insurance_rtrecord"]
        query = {}
        if from_date and to_date:
            try:
                from_dt = datetime.strptime(from_date, "%Y-%m-%d")
                to_dt = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)
                
                from_date_str = from_date
                to_date_str = to_dt.strftime("%Y-%m-%d")
                
                query["$or"] = [
                    {"date": {"$gte": from_dt, "$lt": to_dt}},
                    {"date": {"$gte": from_date_str, "$lt": to_date_str}}
                ]
            except ValueError:
                pass
                
        records = list(collection.find(query).sort("rt_id", -1))
        records = convert_dates_to_strings(records)
        global_db = get_global_db()
        for r in records:
            if '_id' in r:
                r['_id'] = str(r['_id'])
            # Resolve editHistory edited_by IDs to names
            raw_history = r.get('editHistory')
            if isinstance(raw_history, str):
                try:
                    raw_history = json.loads(raw_history)
                except Exception:
                    raw_history = []
            if isinstance(raw_history, list):
                for h in raw_history:
                    emp_id = str(h.get('edited_by', ''))
                    if emp_id:
                        h['edited_by_name'] = get_employee_name_by_id(emp_id, db=global_db)
                r['editHistory'] = raw_history
                
        return Response({"success": True, "data": records})

    employee_id = get_employee_id(request)
    data = request.data.copy()

    required_fields = ['date', 'patient_name', 'date_of_admission', 'date_of_discharge', 'insurance_type', 'amount_to_be_paid']
    for field in required_fields:
        if not data.get(field):
            return Response({'error': f'{field.replace("_", " ").title()} is mandatory'}, status=status.HTTP_400_BAD_REQUEST)

    data["created_by"] = employee_id
    
    # Remove auth fields and extract payment_details to avoid Djongo JSONField crash
    for field in AUTH_FIELDS:
        data.pop(field, None)
    payment_details = data.pop("payment_details", [])
    
    # Calculate total payments and set status
    expected_amount = 0
    try:
        if data.get("amount_to_be_paid"):
            expected_amount = float(data.get("amount_to_be_paid"))
    except (ValueError, TypeError):
        pass

    total_paid = 0
    for payment in payment_details:
        try:
            if payment.get("amount"):
                total_paid += float(payment.get("amount"))
        except (ValueError, TypeError):
            pass

    if total_paid == 0:
        status_val = "Pending"
    elif total_paid >= expected_amount:
        status_val = "Paid"
    else:
        status_val = "Partially Paid"
    
    # Create record manually with PyMongo to avoid Djongo serializer crashes
    db = get_insurance_db()
    collection = db["insurance_rtrecord"]
    
    # Generate ID
    last = collection.find_one({}, sort=[("rt_id", -1)])
    new_id = (last["rt_id"] + 1) if last else 1
    
    insert_data = {
        "rt_id": new_id,
        "created_by": employee_id,
        "created_date": datetime.now().isoformat(),
        "payment_details": payment_details,
        "status": status_val,
        "patient_name": data.get("patient_name", ""),
        "insurance_type": data.get("insurance_type", ""),
        "specificInsuranceCompany": data.get("specificInsuranceCompany", ""),
        "amount_to_be_paid": data.get("amount_to_be_paid", "")
    }
    
    # Process dates
    if data.get("date"):
        try:
            insert_data["date"] = datetime.strptime(str(data["date"])[:10], "%Y-%m-%d")
        except ValueError:
            pass
    if data.get("date_of_admission"):
        try:
            insert_data["date_of_admission"] = datetime.strptime(str(data["date_of_admission"])[:10], "%Y-%m-%d")
        except ValueError:
            pass
    if data.get("date_of_discharge"):
        try:
            insert_data["date_of_discharge"] = datetime.strptime(str(data["date_of_discharge"])[:10], "%Y-%m-%d")
        except ValueError:
            pass
            
    collection.insert_one(insert_data)
    
    # Return stringified ID in response
    insert_data["rt_id"] = new_id
    if "_id" in insert_data:
        insert_data["_id"] = str(insert_data["_id"])
        
    return Response({"success": True, "message": "RT Record created successfully", "data": insert_data}, status=status.HTTP_201_CREATED)

@api_view(["PUT"])
@csrf_exempt
@permission_classes([HasRolePermission])
def rt_record_update_view(request, pk):
    try:
        pk = int(pk)
    except ValueError:
        pass

    db = get_insurance_db()
    collection = db["insurance_rtrecord"]
    
    record = collection.find_one({"rt_id": pk})
    if not record:
        return Response({"success": False, "error": "RT Record not found"}, status=status.HTTP_404_NOT_FOUND)
        
    employee_id = get_employee_id(request)
    
    # Prepare update data from request
    update_data = {k: v for k, v in request.data.items() if k not in AUTH_FIELDS}

    required_fields = ['date', 'patient_name', 'date_of_admission', 'date_of_discharge', 'insurance_type', 'amount_to_be_paid']
    for field in required_fields:
        if not update_data.get(field, record.get(field)):
            return Response({'error': f'{field.replace("_", " ").title()} is mandatory'}, status=status.HTTP_400_BAD_REQUEST)

    update_data["lastmodified_by"] = employee_id
    update_data["lastmodified_date"] = datetime.now().isoformat()
    
    # Ensure dates are properly formatted
    if "date" in update_data and update_data["date"]:
        try:
            update_data["date"] = datetime.strptime(str(update_data["date"])[:10], "%Y-%m-%d")
        except ValueError:
            pass
    if "date_of_admission" in update_data and update_data["date_of_admission"]:
        try:
            update_data["date_of_admission"] = datetime.strptime(str(update_data["date_of_admission"])[:10], "%Y-%m-%d")
        except ValueError:
            pass
    if "date_of_discharge" in update_data and update_data["date_of_discharge"]:
        try:
            update_data["date_of_discharge"] = datetime.strptime(str(update_data["date_of_discharge"])[:10], "%Y-%m-%d")
        except ValueError:
            pass
            
    # Keep payment details as list if not in update_data
    if "payment_details" not in update_data:
        update_data["payment_details"] = record.get("payment_details", [])
        
    # Calculate total payments and set status
    expected_amount = 0
    try:
        if update_data.get("amount_to_be_paid"):
            expected_amount = float(update_data.get("amount_to_be_paid"))
    except (ValueError, TypeError):
        pass

    total_paid = 0
    for payment in update_data.get("payment_details", []):
        try:
            if payment.get("amount"):
                total_paid += float(payment.get("amount"))
        except (ValueError, TypeError):
            pass

    if total_paid == 0:
        update_data["status"] = "Pending"
    elif total_paid >= expected_amount:
        update_data["status"] = "Paid"
    else:
        update_data["status"] = "Partially Paid"
        
    collection.update_one({"rt_id": pk}, {"$set": update_data})
    
    return Response({"success": True, "message": "RT Record updated successfully"})

@api_view(["GET", "POST"])
@csrf_exempt
@permission_classes([HasRolePermission])
def chemo_record_view(request):
    if request.method == "GET":
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        db = get_insurance_db()
        collection = db["insurance_chemorecord"]
        query = {}
        if from_date and to_date:
            try:
                from_dt = datetime.strptime(from_date, "%Y-%m-%d")
                to_dt = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)
                
                from_date_str = from_date
                to_date_str = to_dt.strftime("%Y-%m-%d")
                
                query["$or"] = [
                    {"date": {"$gte": from_dt, "$lt": to_dt}},
                    {"date": {"$gte": from_date_str, "$lt": to_date_str}}
                ]
            except ValueError:
                pass
                
        records = list(collection.find(query).sort("chemo_id", -1))
        records = convert_dates_to_strings(records)
        global_db = get_global_db()
        for r in records:
            if '_id' in r:
                r['_id'] = str(r['_id'])
            # Resolve editHistory edited_by IDs to names
            raw_history = r.get('editHistory')
            if isinstance(raw_history, str):
                try:
                    raw_history = json.loads(raw_history)
                except Exception:
                    raw_history = []
            if isinstance(raw_history, list):
                for h in raw_history:
                    emp_id = str(h.get('edited_by', ''))
                    if emp_id:
                        h['edited_by_name'] = get_employee_name_by_id(emp_id, db=global_db)
                r['editHistory'] = raw_history
                
        return Response({"success": True, "data": records})

    employee_id = get_employee_id(request)
    data = request.data.copy()

    required_fields = ['date', 'patient_name', 'date_of_admission', 'date_of_discharge', 'insurance_type', 'medicine_details']
    for field in required_fields:
        if not data.get(field):
            return Response({'error': f'{field.replace("_", " ").title()} is mandatory'}, status=status.HTTP_400_BAD_REQUEST)

    data["created_by"] = employee_id
    
    # Remove auth fields and extract payment_details to avoid Djongo JSONField crash
    for field in AUTH_FIELDS:
        data.pop(field, None)
    payment_details = data.pop("payment_details", [])
    
    # Calculate total payments and set status
    expected_amount = 0
    try:
        if data.get("amount_to_be_paid"):
            expected_amount = float(data.get("amount_to_be_paid"))
    except (ValueError, TypeError):
        pass

    total_paid = 0
    for payment in payment_details:
        try:
            if payment.get("amount"):
                total_paid += float(payment.get("amount"))
        except (ValueError, TypeError):
            pass

    if total_paid == 0:
        status_val = "Pending"
    elif total_paid >= expected_amount:
        status_val = "Paid"
    else:
        status_val = "Partially Paid"
    
    # Create record manually with PyMongo to avoid Djongo serializer crashes
    db = get_insurance_db()
    collection = db["insurance_chemorecord"]
    
    # Generate ID
    last = collection.find_one({}, sort=[("chemo_id", -1)])
    new_id = (last["chemo_id"] + 1) if last else 1
    
    insert_data = {
        "chemo_id": new_id,
        "created_by": employee_id,
        "created_date": datetime.now().isoformat(),
        "payment_details": payment_details,
        "status": status_val,
        "patient_name": data.get("patient_name", ""),
        "insurance_type": data.get("insurance_type", ""),
        "specificInsuranceCompany": data.get("specificInsuranceCompany", ""),
        "amount_to_be_paid": data.get("amount_to_be_paid", ""),
        "medicine_details": data.get("medicine_details", "")
    }
    
    # Process dates
    if data.get("date"):
        try:
            insert_data["date"] = datetime.strptime(str(data["date"])[:10], "%Y-%m-%d")
        except ValueError:
            pass
    if data.get("date_of_admission"):
        try:
            insert_data["date_of_admission"] = datetime.strptime(str(data["date_of_admission"])[:10], "%Y-%m-%d")
        except ValueError:
            pass
    if data.get("date_of_discharge"):
        try:
            insert_data["date_of_discharge"] = datetime.strptime(str(data["date_of_discharge"])[:10], "%Y-%m-%d")
        except ValueError:
            pass
            
    collection.insert_one(insert_data)
    
    # Return stringified ID in response
    insert_data["chemo_id"] = new_id
    if "_id" in insert_data:
        insert_data["_id"] = str(insert_data["_id"])
        
    return Response({"success": True, "message": "Chemo Record created successfully", "data": insert_data}, status=status.HTTP_201_CREATED)

@api_view(["PUT"])
@csrf_exempt
@permission_classes([HasRolePermission])
def chemo_record_update_view(request, pk):
    try:
        pk = int(pk)
    except ValueError:
        pass

    db = get_insurance_db()
    collection = db["insurance_chemorecord"]
    
    record = collection.find_one({"chemo_id": pk})
    if not record:
        return Response({"success": False, "error": "Chemo Record not found"}, status=status.HTTP_404_NOT_FOUND)
        
    employee_id = get_employee_id(request)
    
    # Prepare update data from request
    update_data = {k: v for k, v in request.data.items() if k not in AUTH_FIELDS}

    required_fields = ['date', 'patient_name', 'date_of_admission', 'date_of_discharge', 'insurance_type', 'medicine_details']
    for field in required_fields:
        if not update_data.get(field, record.get(field)):
            return Response({'error': f'{field.replace("_", " ").title()} is mandatory'}, status=status.HTTP_400_BAD_REQUEST)

    update_data["lastmodified_by"] = employee_id
    update_data["lastmodified_date"] = datetime.now().isoformat()
    
    # Ensure dates are properly formatted
    if "date" in update_data and update_data["date"]:
        try:
            update_data["date"] = datetime.strptime(str(update_data["date"])[:10], "%Y-%m-%d")
        except ValueError:
            pass
    if "date_of_admission" in update_data and update_data["date_of_admission"]:
        try:
            update_data["date_of_admission"] = datetime.strptime(str(update_data["date_of_admission"])[:10], "%Y-%m-%d")
        except ValueError:
            pass
    if "date_of_discharge" in update_data and update_data["date_of_discharge"]:
        try:
            update_data["date_of_discharge"] = datetime.strptime(str(update_data["date_of_discharge"])[:10], "%Y-%m-%d")
        except ValueError:
            pass
            
    # Keep payment details as list if not in update_data
    if "payment_details" not in update_data:
        update_data["payment_details"] = record.get("payment_details", [])
        
    # Calculate total payments and set status
    expected_amount = 0
    try:
        if update_data.get("amount_to_be_paid"):
            expected_amount = float(update_data.get("amount_to_be_paid"))
    except (ValueError, TypeError):
        pass

    total_paid = 0
    for payment in update_data.get("payment_details", []):
        try:
            if payment.get("amount"):
                total_paid += float(payment.get("amount"))
        except (ValueError, TypeError):
            pass

    if total_paid == 0:
        update_data["status"] = "Pending"
    elif total_paid >= expected_amount:
        update_data["status"] = "Paid"
    else:
        update_data["status"] = "Partially Paid"
        
    collection.update_one({"chemo_id": pk}, {"$set": update_data})
    
    return Response({"success": True, "message": "Chemo Record updated successfully"})