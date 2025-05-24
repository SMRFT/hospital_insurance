from django.db import models


class AuditModel(models.Model):
    created_by = models.CharField(max_length=100, blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    lastmodified_by = models.CharField(max_length=100, blank=True, null=True)
    lastmodified_date = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.created_by:
            self.created_by = "system"
        self.lastmodified_by = self.lastmodified_by or "system"
        super().save(*args, **kwargs)

#Register
class Register(AuditModel):
    id = models.CharField(max_length=500, primary_key=True)
    name = models.CharField(max_length=500)
    role = models.CharField(max_length=500)
    email = models.EmailField(max_length=500, unique=True)
    password = models.CharField(max_length=500)
#Login
class Login(AuditModel):
    email = models.CharField(max_length=150)
    password = models.CharField(max_length=120)
#Insurance
class Insurance(AuditModel):
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
 

class Daycare(AuditModel):
    admissionType = models.JSONField()  # This will store the admission type as JSON
    patientName = models.CharField(max_length=255)
    uhid = models.CharField(max_length=100)
    doctorName = models.CharField(max_length=255)
    companyName = models.CharField(max_length=255, blank=True, null=True)
    specificInsuranceCompany = models.CharField(max_length=255, blank=True, null=True)
    billType = models.CharField(max_length=255, blank=True, null=True)
    claimId = models.CharField(max_length=255, blank=True, null=True)
    opFile = models.CharField(max_length=255, blank=True, null=True)
    submissionDate = models.CharField(max_length=150)
    claimDetails =  models.CharField(max_length=255, blank=True, null=True)
    billAmount = models.CharField(max_length=255, blank=True, null=True)
    claimApproval = models.CharField(max_length=255, blank=True, null=True)
    
    def __str__(self):
        return self.patientName
