from django.urls import path
from django.urls import re_path
from . import views

urlpatterns = [
    path('registration/', views.registration, name='registration'),
    path('login/', views.login, name='login'),
    path('insurance/', views.insurance, name="Insurance"),
    path('insurance/check_exists/', views.check_patient_exists, name = "check_patient_exists"),
    path('get_insurance_companies/', views.get_insurance_companies, name="get_insurance_companies"),
    path('insurance/serve_file/<str:file_id>/', views.serve_file, name="serve_file"),  # Add this line for file serving
    path('submit-daycare/', views.submit_daycare, name='submit_daycare'),
    re_path(r'^insurance/update/(?P<identifier>.+)/$', views.insurance_update_combined, name='insurance_update_combined'),
    re_path(r'^insurance/update_pendingamount/(?P<identifier>.+)/$', views.insurance_update_combined, name='insurance_update'),
    path('other_records/', views.other_record_view, name='other_records'),
    path('other_records/report/', views.other_record_report_view, name='other_records_report'),
]
