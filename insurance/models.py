from django.db import models


# models.py
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


class Insurance(AuditModel):
    patient_uhid = models.CharField(max_length=255, blank=True, null=True)
    patient_name = models.CharField(max_length=255, blank=True, null=True)
    billNumber = models.CharField(max_length=255, blank=True, null=True)
    ctseType = models.CharField(max_length=50, blank=True, null=True)
    date = models.CharField(max_length=255, blank=True, null=True)
    companyName = models.CharField(max_length=255, blank=True, null=True)
    specificInsuranceCompany = models.CharField(max_length=255, blank=True, null=True)
    dateOfDischarge = models.CharField(max_length=255, blank=True, null=True)
    claimId = models.CharField(max_length=255, blank=True, null=True)
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
    remarks = models.TextField(blank=True, null=True)
    pendingAmount = models.CharField(max_length=255, blank=True, null=True)
    voucherNumber = models.CharField(max_length=255, blank=True, null=True)
    referral = models.CharField(max_length=255, blank=True, null=True)
    grossAmount = models.CharField(max_length=255, blank=True, null=True)
    taxAmount = models.CharField(max_length=255, blank=True, null=True)
    netAmount = models.CharField(max_length=255, blank=True, null=True)
    gst = models.CharField(max_length=255, blank=True, null=True)
    editHistory = models.JSONField(default=list)


#Daycare
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
    

#OtherReport
class OtherRecord(AuditModel):
    date = models.DateField(blank=True, null=True)
    ip_op_type = models.CharField(max_length=2, choices=[('IP', 'IP'), ('OP', 'OP')], blank=True, null=True)
    patient_uhid = models.CharField(max_length=50)
    patient_name = models.CharField(max_length=200)
    mobile_number = models.CharField(max_length=15)
    doctor_name = models.CharField(max_length=200, blank=True, null=True)
    company_name = models.CharField(max_length=200)
    treatment = models.CharField(max_length=500)
    has_refund = models.BooleanField(default=False)
    refund = models.CharField(max_length=500, blank=True, null=True)
    payment_details = models.JSONField(default=list)
    status = models.CharField(max_length=20, default='Pending')
    
    is_approved = models.BooleanField(default=False)
    approved_by = models.CharField(max_length=500, blank=True, null=True)
    approved_date = models.DateTimeField(blank=True, null=True)

    is_finalapproved = models.BooleanField(default=False)
    final_approved_by = models.CharField(max_length=500, blank=True, null=True)
    final_approved_date = models.DateTimeField(blank=True, null=True)

    is_refund_initiated = models.BooleanField(default=False)
    refund_initiated_by = models.CharField(max_length=500, blank=True, null=True)
    refund_initiated_date = models.DateTimeField(blank=True, null=True)

    is_refund_approved = models.BooleanField(default=False)
    refund_approved_by = models.CharField(max_length=500, blank=True, null=True)
    refund_approved_date = models.DateTimeField(blank=True, null=True)
    editHistory = models.JSONField(default=list)

    def __str__(self):
        return f"{self.patient_name} - {self.patient_uhid}"

    @property
    def total_amount(self):
        """Calculate total amount from payment details"""
        if not self.payment_details:
            return 0
        return sum(float(payment.get('amount', 0)) for payment in self.payment_details)
    
class Enquiry(AuditModel):
    
    enquiry_id = models.IntegerField(primary_key=True)
    date = models.DateField()

    ipNumber = models.CharField(max_length=100, null=True, blank=True)
    opNumber = models.CharField(max_length=100, null=True, blank=True)

    patientName = models.CharField(max_length=255)
    phoneNumber = models.CharField(max_length=15)

    insuranceName = models.CharField(max_length=100, null=True, blank=True)
    treatment = models.CharField(max_length=500, blank=True, null=True)
    specificInsuranceCompany = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    reasonForApproach = models.TextField()

    def save(self, *args, **kwargs):
        if self.enquiry_id is None:
            last = Enquiry.objects.order_by('-enquiry_id').first()
            self.enquiry_id = (last.enquiry_id + 1) if last else 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.patientName
 
 
class FollowUp(AuditModel):
    """One row per follow-up entry. Many follow-ups per Enquiry."""
    followup_id     = models.IntegerField(primary_key=True)
    enquiry         = models.ForeignKey(
        Enquiry, on_delete=models.CASCADE, related_name="follow_ups"
    )
    followup_date    = models.DateField(null=True, blank=True)
    followup_Remarks = models.TextField(null=True, blank=True)
 
    def save(self, *args, **kwargs):
        if self.followup_id is None:
            last = FollowUp.objects.order_by('-followup_id').first()
            self.followup_id = (last.followup_id + 1) if last else 1
        super().save(*args, **kwargs)
 
    def __str__(self):
        return f"FollowUp {self.followup_id} → Enquiry {self.enquiry_id}"

# New Models for RT and Chemo
class RTRecord(AuditModel):
    rt_id = models.IntegerField(primary_key=True)
    date = models.DateField()
    patient_name = models.CharField(max_length=255)
    date_of_admission = models.DateField()
    date_of_discharge = models.DateField()
    insurance_type = models.CharField(max_length=255)
    amount_to_be_paid = models.CharField(max_length=255)
    payment_details = models.JSONField(default=list)
    status = models.CharField(max_length=50, default='Pending')
    editHistory = models.JSONField(default=list)

    def __str__(self):
        return self.patient_name

    def save(self, *args, **kwargs):
        if self.rt_id is None:
            last = RTRecord.objects.order_by('-rt_id').first()
            self.rt_id = (last.rt_id + 1) if last else 1
        super().save(*args, **kwargs)

class ChemoRecord(AuditModel):
    chemo_id = models.IntegerField(primary_key=True)
    date = models.DateField()
    patient_name = models.CharField(max_length=255)
    date_of_admission = models.DateField()
    date_of_discharge = models.DateField()
    insurance_type = models.CharField(max_length=255)
    amount_to_be_paid = models.CharField(max_length=255, blank=True, null=True)
    medicine_details = models.TextField()
    payment_details = models.JSONField(default=list)
    status = models.CharField(max_length=50, default='Pending')
    editHistory = models.JSONField(default=list)

    def __str__(self):
        return self.patient_name

    def save(self, *args, **kwargs):
        if self.chemo_id is None:
            last = ChemoRecord.objects.order_by('-chemo_id').first()
            self.chemo_id = (last.chemo_id + 1) if last else 1
        super().save(*args, **kwargs)