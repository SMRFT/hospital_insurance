from django.urls import path
from django.urls import re_path
from . import views

urlpatterns = [
    path('registration/', views.registration, name='registration'),
    path('login/', views.login, name='login'),
    path('insurance/', views.insurance, name="Insurance"),
    path('get_insurance_companies/', views.get_insurance_companies, name="get_insurance_companies"),
    path('insurance/serve_file/<str:file_id>/', views.serve_file, name="serve_file"),  # Add this line for file serving
    path('submit-daycare/', views.submit_daycare, name='submit_daycare'),
    re_path(r'^insurance/update/(?P<identifier>.+)/$', views.insurance_update_combined, name='insurance_update_combined'),
    re_path(r'^insurance/update_pendingamount/(?P<identifier>.+)/$', views.insurance_update_combined, name='insurance_update'),
]
