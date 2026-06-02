from django.urls import path
from django.urls import re_path
from . import views

urlpatterns = [
    path('insurance/', views.insurance, name="Insurance"),
    path('get_insurance_companies/', views.get_insurance_companies, name="get_insurance_companies"),
    path('insurance/serve_file/<str:file_id>/', views.serve_file, name="serve_file"), 
    re_path(r'^insurance/update/(?P<identifier>.+)/$', views.insurance_update_combined, name='insurance_update_combined'),
    path('other_records/', views.other_record_view, name='other_records'),
    path('other_records/overall_approval/',views.overall_approval_view,name='overall_approval'),
    path('other_records/refund_approval/',views.refund_approval_view,name='refund_approval'),
    path('other_records/final_approval/',views.final_approval_view,name='final_approval'),
    path('other_records/refund_approval_update/',views.refund_approval_update_view,name='refund_approval_update'),
    path('other_records/collected_finalapproved/',views.collected_finalapproved_view,name='refund_approval_update'),
    path('other_records/report/', views.other_record_report_view, name='other_records_report'),
    path('get_doctor_list/', views.get_doctor_list, name='get_doctor_list'),
    path('get_treatment_list/', views.get_treatment_list, name='get_treatment_list'),
    path('add_doctor/',         views.add_doctor,         name='add_doctor'),
    path('add_treatment/',      views.add_treatment,      name='add_treatment'),
    path("enquiry/", views.enquiry_view, name="enquiry"),
    path("enquiry_list/", views.enquiry_list, name="enquiry_list"),
    path("enquiry/<int:enquiry_id>/follow_ups/", views.followup_view, name="followup_list"),
    path("enquiry/<int:enquiry_id>/follow_ups/<int:followup_id>/",views.followup_detail_view,name="followup_detail"),
]
