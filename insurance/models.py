from django.db import models
from django.contrib.postgres.fields import JSONField  # PostgreSQL-specific
#Register
class Register(models.Model):
    id = models.CharField(max_length=500, primary_key=True)
    name = models.CharField(max_length=500)
    role = models.CharField(max_length=500)
    email = models.EmailField(max_length=500, unique=True)
    password = models.CharField(max_length=500)
    confirmPassword = models.CharField(max_length=500)
#Login
class Login(models.Model):
    email = models.CharField(max_length=150)
    password = models.CharField(max_length=120)
#Insurance
class Insurance(models.Model):
    patient_uhid = models.CharField(max_length=255, blank=True, null=True)
    patient_name = models.CharField(max_length=255, blank=True, null=True)
    billNumber = models.CharField(max_length=255, blank=True, null=True)
    date = models.CharField(max_length=255, blank=True, null=True)
    companyName = models.CharField(max_length=255, blank=True, null=True)
    specificInsuranceCompany = models.CharField(max_length=255, blank=True, null=True)
    dateOfDischarge = models.CharField(max_length=255, blank=True, null=True)
    billingFile = models.CharField(max_length=255, blank=True, null=True)
    queryUpload = models.CharField(max_length=255, blank=True, null=True)
    queryResponse = models.CharField(max_length=255, blank=True, null=True)
    submissionStatus = models.CharField(max_length=255, default="Online")
    approvalAmount = models.CharField(max_length=255, blank=True, null=True)
    claimedAmount = models.CharField(max_length=255, blank=True, null=True)
    settledAmount = models.CharField(max_length=255, blank=True, null=True)
    approval = models.CharField(max_length=255, default="As per norm")
    followUp = models.CharField(max_length=255, blank=True, null=True)
    reasonNotMatch = models.CharField(max_length=255, blank=True, null=True)
    claimOption = models.CharField(max_length=255, default="Not Claim")
    claimDetails = models.CharField(max_length=255, blank=True, null=True)
    notClaimReason = models.CharField(max_length=255, blank=True, null=True)
    opNumber = models.CharField(max_length=255, blank=True, null=True)
    ipNumber = models.CharField(max_length=255, blank=True, null=True)
    billDate = models.CharField(max_length=255, blank=True, null=True)
    billAmount = models.CharField(max_length=255, blank=True, null=True)
    fileSubmissionDate = models.CharField(max_length=255, blank=True, null=True)
    queryDate = models.CharField(max_length=255, blank=True, null=True)
    approvalDate = models.CharField(max_length=255, blank=True, null=True)
    treatmentType = models.CharField(max_length=255, blank=True, null=True)
    radiotherapyCycles = models.CharField(max_length=255, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)  # Longer remarks field
    pendingAmount = models.CharField(max_length=255, blank=True, null=True)
    editHistory = models.JSONField(default=list) 
 

class Daycare(models.Model):
    admissionType = models.JSONField()  # This will store the admission type as JSON
    patientName = models.CharField(max_length=255)
    uhid = models.CharField(max_length=100)
    doctorName = models.CharField(max_length=255)
    companyName = models.CharField(max_length=255, blank=True, null=True)
    specificInsuranceCompany = models.CharField(max_length=255, blank=True, null=True)
    billType = models.CharField(max_length=50)
    claimId = models.CharField(max_length=100)
    opFile = models.CharField(max_length=255, blank=True, null=True) 
    submissionDate = models.DateField()
    claimDetails = models.CharField(max_length=50)
    billAmount = models.CharField(max_length=50)
    claimApproval = models.CharField(max_length=50)
    
    def __str__(self):
        return self.patient_name
